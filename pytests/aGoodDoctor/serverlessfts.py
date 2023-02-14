'''
Created on May 31, 2022

@author: ritesh.agarwal
'''

import itertools
import json
import random
from threading import Thread
import threading
import time

from Cb_constants.CBServer import CbServer
from FtsLib.FtsOperations import FtsHelper
from TestInput import TestInputSingleton
from com.couchbase.client.core.deps.io.netty.handler.timeout import TimeoutException
from com.couchbase.client.core.error import AmbiguousTimeoutException, \
 RequestCanceledException, CouchbaseException, UnambiguousTimeoutException
from com.couchbase.client.java.search import SearchQuery
from global_vars import logger
from sdk_client3 import SDKClient
from table_view import TableView
from membase.api.rest_client import RestConnection


ftsQueries = [
            SearchQuery.queryString("pJohn"),
            SearchQuery.match("pJohn"),
            SearchQuery.prefix("Cari")
            ]


class DoctorFTS:

    def __init__(self, cluster, bucket_util):
        self.cluster = cluster
        self.bucket_util = bucket_util
        self.input = TestInputSingleton.input
        self.fts_index_partitions = self.input.param("fts_index_partition", 1)
        self.log = logger.get("test")
        self.stop_run = False

    def monitor_fts_auto_scaling(self, dataplane_id):
        '''
        1. Monitor when the FTS scaling should trigger.
        2. Wait for FTS scaling to trigger
        3. Assert the number of FTS nodes in the cluster
        '''
        pass

    def create_fts_indexes(self, buckets):
        for b in buckets:
            i = 0
            b.ftsIndexes = dict()
            b.ftsQueries = dict()
            if b.loadDefn.get("FTS")[0] == 0:
                continue
            self.log.info("Creating FTS indexes on {}".format(b.name))
            self.fts_helper = FtsHelper(b.serverless.nebula_endpoint)
            for s in self.bucket_util.get_active_scopes(b, only_names=True):
                for c in sorted(self.bucket_util.get_active_collections(b, s, only_names=True)):
                    if c == CbServer.default_collection:
                        continue
                    fts_param_template = self.get_fts_idx_template()
                    fts_param_template.update({
                        "name": str(b.name.replace("-", "_")) + "_fts_idx_{}".format(i), "sourceName": str(b.name)})
                    fts_param_template["planParams"].update({
                        "indexPartitions": self.fts_index_partitions})
                    fts_param_template["params"]["mapping"]["types"].update({
                        "%s.%s" % (s, c): {
                            "dynamic": True, "enabled": True}
                        }
                    )
                    fts_param_template = str(fts_param_template).replace("True", "true")
                    fts_param_template = str(fts_param_template).replace("False", "false")
                    fts_param_template = str(fts_param_template).replace("'", "\"")
                    self.log.debug("Creating fts index: {}".format(b.name.replace("-", "_") + "_fts_idx_"+str(i)))
                    retry = 10
                    while retry > 0:
                        status, _ = self.fts_helper.create_fts_index_from_json(
                            b.name.replace("-", "_")+"_fts_idx_"+str(i), str(fts_param_template))
                        if status is False:
                            self.log.critical("FTS index creation failed")
                            time.sleep(10)
                            retry -= 1
                        else:
                            b.ftsIndexes.update({str(b.name).replace("-", "_")+"_fts_idx_"+str(i): (fts_param_template, b.name, s, c)})
                            break
                    i += 1
                    time.sleep(10)
                    if i >= b.loadDefn.get("FTS")[0]:
                        break
                if i >= b.loadDefn.get("FTS")[0]:
                    break

    def discharge_FTS(self):
        self.stop_run = True

    def get_fts_idx_template(self):
        fts_idx_template = {
            "type": "fulltext-index",
            "name": "fts-index",
            "sourceType": "gocbcore",
            "sourceName": "default",
            "planParams": {
                "maxPartitionsPerPIndex": 1024,
                "indexPartitions": 1,
                "numReplicas": 1
             },
            "params": {
                "doc_config": {
                    "docid_prefix_delim": "",
                    "docid_regexp": "",
                    "mode": "scope.collection.type_field",
                    "type_field": "type"
                    },
                "mapping": {
                    "analysis": {},
                    "default_analyzer": "standard",
                    "default_datetime_parser": "dateTimeOptional",
                    "default_field": "_all",
                    "default_mapping": {
                        "dynamic": True,
                        "enabled": False
                        },
                    "default_type": "_default",
                    "docvalues_dynamic": False,
                    "index_dynamic": True,
                    "store_dynamic": False,
                    "type_field": "_type",
                    "types": {}
                    },
                "store": {
                    "indexType": "scorch",
                    "segmentVersion": 15
                    }
                },
            "sourceParams": {}
           }
        return fts_idx_template

    def wait_for_fts_index_online(self, buckets, timeout=86400,
                                  overRideCount=None):
        status = True
        for bucket in buckets:
            self.fts_helper = FtsHelper(bucket.serverless.nebula_endpoint)
            for index_name, details in bucket.ftsIndexes.items():
                status = False
                stop_time = time.time() + timeout
                while time.time() < stop_time:
                    _status, content = self.fts_helper.fts_index_item_count(
                        "%s" % (index_name))
                    self.log.debug("index: {}, status: {}, count: {}"
                                   .format(index_name, _status,
                                           json.loads(content)["count"]))
                    if overRideCount is not None and overRideCount == json.loads(content)["count"] or\
                       json.loads(content)["count"] == bucket.loadDefn.get("num_items"):
                        self.log.info("FTS index is ready: {}".format(index_name))
                        status = True
                        break
                    time.sleep(5)
                if status is False:
                    return status
        return status

    def drop_fts_indexes(self, idx_name):
        """
        Drop count number of fts indexes using fts name
        from fts_dict
        """
        self.log.debug("Dropping fts index: {}".format(idx_name))
        status, _ = self.fts_helper.delete_fts_index(idx_name)
        return status

    def index_stats(self, dataplanes):
        for dataplane in dataplanes.values():
            stat_monitor = threading.Thread(target=self.log_index_stats,
                                            kwargs=dict(dataplane=dataplane,
                                                        print_duration=60))
            stat_monitor.start()

    def log_index_stats(self, dataplane, print_duration=600):
        st_time = time.time()
        self.scale_down = False
        self.scale_up = False
        self.fts_auto_rebl = False
        mem_prof = True
        while not self.stop_run:
            self.scale_down_count = 0
            self.scale_up_count = 0
            self.hwm_count = 0
            collect_logs = False
            if st_time + print_duration < time.time():
                self.table = TableView(self.log.info)
                self.table.set_headers(["Dataplane",
                                        "Node",
                                        "memoryBytes",
                                        "diskBytes",
                                        "billableUnitsRate",
                                        "cpuPercent"])
                for node in dataplane.fts_nodes:
                    try:
                        rest = RestConnection(node)
                        content = rest.get_fts_stats()
                        mem_used = content["utilization:memoryBytes"]*1.0/content["limits:memoryBytes"]
                        cpu_used = content["utilization:cpuPercent"]
                        if mem_used > 1.0 and mem_prof:
                            self.log.critical("This should trigger FTS memory profile capture")
                            FtsHelper(node).capture_memory_profile()
                            collect_logs = True
                            mem_prof = False
                        if self.scale_down is False and self.scale_up is False:
                            if mem_used < 0.3 and cpu_used < 30:
                                self.scale_down_count += 1
                                self.log.info("FTS - Nodes below UWM: {}".format(self.scale_down_count))
                            elif mem_used > 0.5 or cpu_used > 50:
                                self.scale_up_count += 1
                                self.log.info("FTS - Nodes above LWM: {}".format(self.scale_up_count))
                            elif mem_used > 0.8 or cpu_used > 80:
                                self.hwm_count += 1
                            if self.scale_down_count == len(dataplane.fts_nodes)\
                                    and self.scale_down is False\
                                    and len(dataplane.fts_nodes) > 2:
                                self.scale_down = True
                                self.log.info("FTS - Scale DOWN should trigger in a while")
                            if len(dataplane.fts_nodes) < 10\
                               and self.scale_up_count == len(dataplane.fts_nodes)\
                               and self.scale_up is False:
                                self.scale_up = True
                                self.log.info("FTS - Scale UP should trigger in a while")
                            if self.hwm_count > 0 and self.fts_auto_rebl is False:
                                self.fts_auto_rebl = True
                                self.log.info("FTS - Auto-Rebalance should trigger in a while")
                        self.table.add_row([
                            dataplane.id,
                            node.ip,
                            "{}/{}".format(str(content["utilization:memoryBytes"]/1024/1024),
                                           str(content["limits:memoryBytes"]/1024/1024)),
                            "{}/{}".format(str(content["utilization:diskBytes"]/1024/1024),
                                           str(content["limits:diskBytes"]/1024/1024)),
                            "{}/{}".format(str(content["utilization:billableUnitsRate"]),
                                           str(content["limits:billableUnitsRate"])),
                            "{}".format(str(content["utilization:cpuPercent"]))
                            ])
                    except Exception as e:
                        self.log.critical(e)
                self.table.display("FTS Statistics")
                st_time = time.time()
            if collect_logs:
                self.log.critical("Please collect logs immediately!!!")
                pass


class FTSQueryLoad:
    def __init__(self, bucket):
        self.bucket = bucket
        self.failed_count = itertools.count()
        self.success_count = itertools.count()
        self.rejected_count = itertools.count()
        self.error_count = itertools.count()
        self.cancel_count = itertools.count()
        self.timeout_count = itertools.count()
        self.total_query_count = 0
        self.stop_run = False
        self.cluster_conn = SDKClient([bucket.serverless.nebula_endpoint], None).cluster
        self.log = logger.get("infra")

    def start_query_load(self):
        th = threading.Thread(target=self._run_concurrent_queries,
                              kwargs=dict(bucket=self.bucket))
        th.start()

        monitor = threading.Thread(target=self.monitor_query_status,
                                   kwargs=dict(print_duration=600))
        monitor.start()

    def stop_query_load(self):
        self.stop_run = True
        try:
            if self.cluster_conn:
                self.cluster_conn.close()
        except:
            pass

    def _run_concurrent_queries(self, bucket):
        threads = []
        self.total_query_count = 0
        self.concurrent_queries_to_run = bucket.loadDefn.get("FTS")[1]
        self.currently_running = 0
        query_count = 0
        for i in range(0, self.concurrent_queries_to_run):
            self.total_query_count += 1
            self.currently_running += 1
            query = random.choice(ftsQueries)
            index, details = random.choice(bucket.ftsIndexes.items())
            _, b, s, _ = details
            threads.append(Thread(
                target=self._run_query,
                name="query_thread_{0}".format(self.total_query_count),
                args=(index, query, b, s)))

        i = 0
        for thread in threads:
            i += 1
            thread.start()
            query_count += 1

        i = 0
        while not self.stop_run:
            threads = []
            new_queries_to_run = self.concurrent_queries_to_run - self.currently_running
            for i in range(0, new_queries_to_run):
                query = random.choice(ftsQueries)
                index, details = random.choice(bucket.ftsIndexes.items())
                _, b, s, _ = details
                self.total_query_count += 1
                threads.append(Thread(
                    target=self._run_query,
                    name="query_thread_{0}".format(self.total_query_count),
                    args=(index, query, b, s)))
            i = 0
            self.currently_running += new_queries_to_run
            for thread in threads:
                i += 1
                thread.start()

            time.sleep(2)
        if self.failed_count.next()-1>0 or self.error_count.next()-1 > 0:
            raise Exception("Queries Failed:%s , Queries Error Out:%s" %
                            (self.failed_count, self.error_count))

    def _run_query(self, index, query, b, s, validate_item_count=False, expected_count=0):
        start = time.time()
        try:
            result = self.execute_fts_query("{}.{}.{}".format(b, s, index), query)
            if validate_item_count:
                if result.metaData().metrics().totalRows() != expected_count:
                    self.failed_count.next()
                else:
                    self.success_count.next()
            else:
                self.success_count.next()
        except TimeoutException or AmbiguousTimeoutException or UnambiguousTimeoutException as e:
            self.timeout_count.next()
        except RequestCanceledException as e:
                self.cancel_count.next()
        except CouchbaseException as e:
                self.rejected_count.next()
        except Exception as e:
            print(e)
            self.error_count.next()
        end = time.time()
        if end - start < 1:
            time.sleep(end - start)
        self.currently_running -= 1

    def execute_fts_query(self, index, query):
        """
        Executes a statement on CBAS using the REST API using REST Client
        """
        result = self.cluster_conn.searchQuery(index, query)
        return result

    def monitor_query_status(self, print_duration=600):
        st_time = time.time()
        while not self.stop_run:
            if st_time + print_duration < time.time():
                self.table = TableView(self.log.info)
                self.table.set_headers(["Bucket",
                                        "Total Queries",
                                        "Failed Queries",
                                        "Success Queries",
                                        "Rejected Queries",
                                        "Cancelled Queries",
                                        "Timeout Queries",
                                        "Errored Queries"])
                self.table.add_row([
                    str(self.bucket.name),
                    str(self.total_query_count),
                    str(self.failed_count),
                    str(self.success_count),
                    str(self.rejected_count),
                    str(self.cancel_count),
                    str(self.timeout_count),
                    str(self.error_count),
                    ])
                self.table.display("FTS Query Statistics")
                st_time = time.time()
