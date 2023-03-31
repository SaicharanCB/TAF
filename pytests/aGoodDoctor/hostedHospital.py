'''
Created on May 2, 2022

@author: ritesh.agarwal
'''

from basetestcase import BaseTestCase
from membase.api.rest_client import RestConnection
import threading
from aGoodDoctor.bkrs import DoctorBKRS
import os
from BucketLib.bucket import Bucket
from capella_utils.dedicated import CapellaUtils as CapellaAPI
from aGoodDoctor.fts import DoctorFTS
from aGoodDoctor.hostedN1QL import QueryLoad, DoctorN1QL
from aGoodDoctor.hostedCbas import DoctorCBAS
from aGoodDoctor.hostedOPD import OPD


class Murphy(BaseTestCase, OPD):

    def init_doc_params(self):
        self.create_perc = self.input.param("create_perc", 100)
        self.update_perc = self.input.param("update_perc", 20)
        self.delete_perc = self.input.param("delete_perc", 20)
        self.expiry_perc = self.input.param("expiry_perc", 20)
        self.read_perc = self.input.param("read_perc", 20)
        self.start = 0
        self.end = 0
        self.initial_items = self.start
        self.final_items = self.end
        self.create_end = 0
        self.create_start = 0
        self.update_end = 0
        self.update_start = 0
        self.delete_end = 0
        self.delete_start = 0
        self.expire_end = 0
        self.expire_start = 0

    def setUp(self):
        BaseTestCase.setUp(self)
        self.init_doc_params()

        self.num_collections = self.input.param("num_collections", 1)
        self.xdcr_collections = self.input.param("xdcr_collections", self.num_collections)
        self.num_collections_bkrs = self.input.param("num_collections_bkrs", self.num_collections)
        self.num_scopes = self.input.param("num_scopes", 1)
        self.xdcr_scopes = self.input.param("xdcr_scopes", self.num_scopes)
        self.num_buckets = self.input.param("num_buckets", 1)
        self.kv_nodes = self.nodes_init
        self.cbas_nodes = self.input.param("cbas_nodes", 0)
        self.fts_nodes = self.input.param("fts_nodes", 0)
        self.index_nodes = self.input.param("index_nodes", 0)
        self.backup_nodes = self.input.param("backup_nodes", 0)
        self.xdcr_remote_nodes = self.input.param("xdcr_remote_nodes", 0)
        self.num_indexes = self.input.param("num_indexes", 0)
        self.mutation_perc = 100
        self.doc_ops = self.input.param("doc_ops", "create")
        if self.doc_ops:
            self.doc_ops = self.doc_ops.split(':')

        self.threads_calculation()
        self.op_type = self.input.param("op_type", "create")
        self.dgm = self.input.param("dgm", None)
        self.num_buckets = self.input.param("num_buckets", 1)
        self.mutate = 0
        self.iterations = self.input.param("iterations", 10)
        self.step_iterations = self.input.param("step_iterations", 1)
        self.rollback = self.input.param("rollback", True)
        self.vbucket_check = self.input.param("vbucket_check", True)
        self.end_step = self.input.param("end_step", None)
        self.key_prefix = "Users"
        self.crashes = self.input.param("crashes", 20)
        self.check_dump_thread = True
        self.skip_read_on_error = False
        self.suppress_error_table = False
        self.track_failures = self.input.param("track_failures", True)
        self.loader_dict = None
        self.parallel_reads = self.input.param("parallel_reads", False)
        self._data_validation = self.input.param("data_validation", True)
        self.fragmentation = int(self.input.param("fragmentation", 50))
        self.key_type = self.input.param("key_type", "SimpleKey")
        self.val_type = self.input.param("val_type", "SimpleValue")
        self.ops_rate = self.input.param("ops_rate", 10000)
        self.gtm = self.input.param("gtm", False)
        self.cursor_dropping_checkpoint = self.input.param(
            "cursor_dropping_checkpoint", None)
        self.index_timeout = self.input.param("index_timeout", 3600)
        self.assert_crashes_on_load = self.input.param("assert_crashes_on_load",
                                                       True)
        self.load_defn = list()
        self.loadDefn1 = {
            "valType": "Hotel",
            "scopes": 1,
            "collections": 2,
            "num_items": 1500000000,
            "start": 0,
            "end": 1500000000,
            "ops": 100000,
            "doc_size": 1024,
            "pattern": [0, 80, 20, 0, 0], # CRUDE
            "load_type": ["update"],
            "2i": (10, 10),
            "FTS": (10, 10)
            }
        self.sanity = {
            "valType": "SimpleValue",
            "scopes": 1,
            "collections": 10,
            "num_items": 10000000,
            "start": 0,
            "end": 10000000,
            "ops": 40000,
            "doc_size": 1024,
            "pattern": [0, 80, 20, 0, 0], # CRUDE
            "load_type": ["update"],
            "2i": (10, 10),
            "FTS": (10, 10)
            }
        sanity = self.input.param("sanity", False)
        if sanity:
            self.load_defn.append(self.sanity)
        else:
            self.load_defn.append(self.loadDefn1)

        if self.xdcr_remote_nodes > 0:
            pass
        #######################################################################
        self.PrintStep("Step 2: Create required buckets and collections.")
        self.log.info("Create CB buckets")
        # Create Buckets
        self.log.info("Get the available memory quota")
        rest = RestConnection(self.cluster.master)
        self.info = rest.get_nodes_self()

        # threshold_memory_vagrant = 100
        kv_memory = self.info.memoryQuota - 100
        ramQuota = self.input.param("ramQuota", kv_memory)
        buckets = ["default"]*self.num_buckets
        bucket_type = self.bucket_type.split(';')*self.num_buckets
        for i in range(self.num_buckets):
            bucket = Bucket(
                {Bucket.name: buckets[i] + str(i),
                 Bucket.ramQuotaMB: ramQuota/self.num_buckets,
                 Bucket.maxTTL: self.bucket_ttl,
                 Bucket.replicaNumber: self.num_replicas,
                 Bucket.storageBackend: self.bucket_storage,
                 Bucket.evictionPolicy: self.bucket_eviction_policy,
                 Bucket.bucketType: bucket_type[i],
                 Bucket.durabilityMinLevel: self.bucket_durability_level,
                 Bucket.flushEnabled: True,
                 Bucket.fragmentationPercentage: self.fragmentation})
            self.bucket_params = {
                "name": bucket.name,
                "bucketConflictResolution": "seqno",
                "memoryAllocationInMb": bucket.ramQuotaMB,
                "flush": bucket.flushEnabled,
                "replicas": bucket.replicaNumber,
                "storageBackend": bucket.storageBackend,
                "durabilityLevel": bucket.durability_level,
                "timeToLive": {"unit": "seconds", "value": bucket.maxTTL}
                }
            CapellaAPI.create_bucket(self.cluster, self.bucket_params)
            self.bucket_util.get_updated_bucket_server_list(self.cluster, bucket)
            bucket.loadDefn = self.load_defn[i % len(self.load_defn)]
            self.cluster.buckets.append(bucket)

        self.buckets = self.cluster.buckets
        self.create_required_collections(self.cluster)

        if self.cluster.cbas_nodes:
            self.drCBAS = DoctorCBAS(self.cluster, self.bucket_util)

        if self.cluster.backup_nodes:
            self.drBackup = DoctorBKRS(self.cluster)

        if self.cluster.index_nodes:
            self.drIndex = DoctorN1QL(self.cluster, self.bucket_util)

        if self.cluster.fts_nodes:
            self.drFTS = DoctorFTS(self.cluster, self.bucket_util)

        self.ql = list()

    def tearDown(self):
        self.check_dump_thread = False
        self.stop_crash = True
        BaseTestCase.tearDown(self)

    def rebalance_config(self, num):
        initial_services = self.input.param("services", "data")
        services = self.input.param("rebl_services", initial_services)
        server_group_list = list()
        for service_group in services.split("-"):
            service_group = service_group.split(":")
            config = {
                "size": num,
                "services": service_group,
                "compute": self.input.param("compute", "m5.xlarge"),
                "storage": {
                    "type": self.input.param("type", "GP3"),
                    "size": self.input.param("size", 50),
                    "iops": self.input.param("iops", 3000)
                }
            }
            if self.capella_cluster_config["place"]["hosted"]["provider"] != "aws":
                config["storage"].pop("iops")
            server_group_list.append(config)
        return server_group_list

    def build_gsi_index(self, buckets):
        self.drIndex.build_indexes(buckets, wait=True)
        for bucket in buckets:
            if bucket.loadDefn.get("2i")[1] > 0:
                ql = QueryLoad(bucket)
                ql.start_query_load()
                self.ql.append(ql)

    def test_rebalance(self):
        self.loop = 1
        self.skip_read_on_error = True
        self.suppress_error_table = True
        '''
        Create sequential: 0 - 10M
        Final Docs = 10M (0-10M, 10M seq items)
        '''
        self.PrintStep("Step 2: Create %s items: %s" % (self.num_items, self.key_type))
        for bucket in self.cluster.buckets:
            self.generate_docs(doc_ops=["create"],
                               create_start=0,
                               create_end=bucket.loadDefn.get("num_items")/2,
                               bucket=bucket)
        self.perform_load(validate_data=False, buckets=self.cluster.buckets, overRidePattern=[100,0,0,0,0])

        self.PrintStep("Step 3: Create %s items: %s" % (self.num_items, self.key_type))
        for bucket in self.cluster.buckets:
            self.generate_docs(doc_ops=["create"],
                               create_start=bucket.loadDefn.get("num_items")/2,
                               create_end=bucket.loadDefn.get("num_items"),
                               bucket=bucket)

        if self.cluster.fts_nodes:
            self.drFTS.create_fts_indexes()
            status = self.drFTS.wait_for_fts_index_online(self.num_items*2,
                                                          self.index_timeout)
            self.assertTrue(status, "FTS index build failed.")

        if self.cluster.cbas_nodes:
            self.drCBAS.create_datasets()
            result = self.drCBAS.wait_for_ingestion(self.num_items*2,
                                                    self.index_timeout)
            self.assertTrue(result, "CBAS ingestion coulcn't complete in time: %s" % self.index_timeout)
            self.drCBAS.start_query_load()

        if self.cluster.index_nodes:
            self.drIndex.create_indexes(self.cluster.buckets)
            self.build_gsi_index(self.cluster.buckets)

        self.rebl_nodes = self.nodes_init
        self.max_rebl_nodes = self.input.param("max_rebl_nodes",
                                               self.nodes_init + 6)
        self.doc_ops = self.input.param("doc_ops", "expiry").split(":")
        perc = 100/len(self.doc_ops)
        self.expiry_perc = perc
        self.create_perc = perc
        self.update_perc = perc
        self.delete_perc = perc
        self.read_perc = perc

        self.rebl_services = self.input.param("rebl_services", "kv").split("-")
        self.sleep(30)
        self.mutation_perc = self.input.param("mutation_perc", 100)
        while self.loop <= self.iterations:
            self.ops_rate = self.input.param("rebl_ops_rate", self.ops_rate)
            for bucket in self.cluster.buckets:
                self.generate_docs(bucket=bucket)
            tasks = self.perform_load(wait_for_load=False)
            self.rebl_nodes += 3
            if self.rebl_nodes > self.max_rebl_nodes:
                self.rebl_nodes = self.nodes_init
            config = self.rebalance_config(self.rebl_nodes)

            ###################################################################
            self.PrintStep("Step 4.{}: Scale UP with Loading of docs".
                           format(self.loop))
            rebalance_task = self.task.async_rebalance_capella(self.cluster,
                                                               config,
                                                               timeout=5*60*60)

            self.task_manager.get_task_result(rebalance_task)
            self.assertTrue(rebalance_task.result, "Rebalance Failed")
            self.print_stats()
            self.sleep(60, "Sleep for 60s after rebalance")

            self.PrintStep("Step 5.{}: Scale DOWN with Loading of docs".
                           format(self.loop))
            config = self.rebalance_config(self.nodes_init)
            rebalance_task = self.task.async_rebalance_capella(self.cluster,
                                                               config,
                                                               timeout=5*60*60)

            self.task_manager.get_task_result(rebalance_task)
            self.assertTrue(rebalance_task.result, "Rebalance Failed")
            self.print_stats()
            self.sleep(60, "Sleep for 60s after rebalance")

            self.loop += 1
            self.wait_for_doc_load_completion(tasks)
            if self.track_failures:
                self.data_validation()
        if self.cluster.fts_nodes:
            self.drFTS.discharge_FTS()
        if self.cluster.cbas_nodes:
            self.drCBAS.discharge_CBAS()
        if self.cluster.index_nodes:
            self.drIndex.discharge_N1QL()