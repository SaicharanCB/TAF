import random
from serverless.tenant_mgmt_on_cloud import TenantMgmtOnCloud
from org.xbill.DNS import Lookup, Type
from capella_utils.serverless import CapellaUtils as ServerlessUtils
from membase.api.rest_client import RestConnection

from bucket_utils.bucket_ready_functions import DocLoaderUtils
from Cb_constants import CbServer
from com.couchbase.test.docgen import DocumentGenerator
from com.couchbase.test.sdk import Server


class MeteringOnCloud(TenantMgmtOnCloud):

    def setUp(self):
        super(MeteringOnCloud, self).setUp()
        self.db_name = "TAF-MeteringOnCloud"
        self.num_collections = self.input.param("num_collections", 1)
        self.num_scopes = self.input.param("num_scopes", 1)
        self.ops_rate = self.input.param("ops_rate", 1000)
        self.srv = self.input.param("srv", "")
        self.username = self.input.param("username", "")
        self.password = self.input.param("password", "")
        self.bucket_throttling_limit = self.input.param("throttle_limit", 5000)
        # create the required database
        spec = self.get_bucket_spec(bucket_name_format="taf-meter-throttle%s",
                                    num_buckets=self.num_buckets,
                                    scopes_per_bucket=self.num_scopes,
                                    collections_per_scope=self.num_collections)
        self.create_required_buckets(spec)
        self.get_servers_for_databases()
        self.expected_stats = dict()
        for bucket in self.cluster.buckets:
            self.expected_stats[bucket.name] = dict()
            self.expected_stats[bucket.name]["num_throttled"], \
                self.expected_stats[bucket.name]["ru"], \
                self.expected_stats[bucket.name]["wu"] = \
                self.bucket_util.get_stat_from_metrics(bucket)

    def tearDown(self):
        super(MeteringOnCloud, self).tearDown()

    def get_servers_for_databases(self):
        dataplanes_id = dict()
        self.cluster.pod.TOKEN = self.token
        self.serverless_util = ServerlessUtils(self.cluster)
        for bucket in self.cluster.buckets:
            dataplane_id = self.serverless_util.get_database_dataplane_id(self.pod, bucket.name)
            if dataplane_id not in dataplanes_id:
                self.username, self.password, self.srv = self.serverless_util.bypass_dataplane(self.pod,
                                                              dataplane_id)
                dataplanes_id[dataplane_id] = [self.username, self.password, self.srv]
                self.log.info("srv is {}".format(self.srv))
                self.log.info("username {0} and password {0}".format(self.username, self.password))
            records = Lookup("_couchbases._tcp.{}".format(dataplanes_id[dataplane_id][2]), Type.SRV).run()
            self.log.info(records)
            bucket.servers = list()
            server = dict()
            for record in records:
                server["ip"] = str(record.getTarget()).rstrip(".")
                server["username"] = dataplanes_id[dataplane_id][0]
                server["password"] = dataplanes_id[dataplane_id][1]
                server["port"] = 18091
                break
            output = RestConnection(server).get_server_list(bucket.name)
            for node in output:
                server = dict()
                server["ip"] = node.split(":")[0]
                server["username"] = dataplanes_id[dataplane_id][0]
                server["password"] = dataplanes_id[dataplane_id][1]
                server["port"] = 18091
                bucket.servers.append(server)
            self.log.info(bucket.servers)

    def load_data(self, create_start=0, create_end=1000, create_perc=0,
                  read_start=0, read_end=0, read_perc=0,
                  update_start=0, update_end=0, update_perc=0, mutated=0,
                  delete_start=0, delete_end=0, delete_perc=0,
                  data_validation=False, buckets=[]):
        loader_map = dict()
        req_clients_per_bucket = 1
        if len(buckets) > 1:
            self.buckets = buckets
        else:
            self.buckets = self.cluster.buckets

        # Create sdk_client_pool
        if self.sdk_client_pool:
            self.sdk_client_pool = \
                self.bucket_util.initialize_java_sdk_client_pool()

            for bucket in self.cluster.buckets:
                nebula = bucket.serverless.nebula_endpoint
                self.log.info("Using Nebula endpoint %s" % nebula.srv)
                server = Server(nebula.srv, nebula.port,
                                nebula.rest_username,
                                nebula.rest_password,
                                str(nebula.memcached_port))
                self.sdk_client_pool.create_clients(
                    bucket.name, server, req_clients_per_bucket)
            self.sleep(5, "Wait for SDK client pool to warmup")

        for bucket in self.buckets:
            for scope in bucket.scopes.keys():
                for collection in bucket.scopes[scope].collections.keys():
                    if scope == CbServer.system_scope:
                        continue
                    work_load_settings = DocLoaderUtils.get_workload_settings(
                        key=self.key, key_size=self.key_size,
                        doc_size=self.doc_size,
                        create_perc=create_perc, create_start=create_start,
                        create_end=create_end, read_perc=read_perc, read_start=read_start,
                        read_end=read_end, update_start=update_start, update_end=update_end,
                        update_perc=update_perc, mutated=mutated, delete_start=delete_start,
                        delete_end=delete_end, delete_perc=delete_perc, ops_rate=self.ops_rate)
                    dg = DocumentGenerator(work_load_settings,
                                           self.key_type, self.val_type)
                    loader_map.update(
                        {bucket.name + scope + collection: dg})

        DocLoaderUtils.perform_doc_loading(self.doc_loading_tm, loader_map,
                                           self.cluster, self.cluster.buckets,
                                           durability_level=self.durability_level,
                                           async_load=False, validate_results=False,
                                           sdk_client_pool=self.sdk_client_pool)

        if data_validation:
            result = DocLoaderUtils.data_validation(
                self.doc_loading_tm, loader_map, self.cluster,
                buckets=self.cluster.buckets, doc_ops=["create"],
                process_concurrency=self.process_concurrency,
                ops_rate=self.ops_rate, sdk_client_pool=self.sdk_client_pool)
            self.assertTrue(result, "Data validation failed")

    def validate_stats(self):
        for bucket in self.cluster.buckets:
            num_throttled, ru, wu = self.bucket_util.get_stat_from_metrics(bucket)
            print("validating wu %s and expected wu %s"
                  %(wu, self.expected_stats[bucket.name]["wu"]))
            if ru < self.expected_stats[bucket.name]["ru"] or num_throttled < \
                    self.expected_stats[bucket.name]["num_throttled"]:
                self.log.info("num_throttled actual {0} and expected {1}".
                          format(num_throttled,
                                 self.expected_stats[bucket.name]["num_throttled"]))
            self.expected_stats[bucket.name]["num_throttled"] = num_throttled

    def update_expected_throttle_limit(self, bucket, num_items, doc_size):
        if self.bucket_util.get_throttle_limit(bucket) in [-1, 2147483647]:
            self.expected_stats[bucket.name]["num_throttled"] += 0
        else:
            self.expected_stats[bucket.name]["num_throttled"] += \
                ((num_items * doc_size) / self.bucket_util.get_throttle_limit(bucket)) * 10

    def update_expected_stat(self, key_size, doc_size, start, end,
                                         write_bucket=[], read_bucket=[]):
        num_items = (end - start) * (self.num_scopes * self.num_collections + 1)
        for bucket in write_bucket:
            self.expected_stats[bucket.name]["wu"] += \
                self.bucket_util.calculate_units(key_size,
                                                        doc_size,
                                                        durability=self.durability_level) * num_items
            self.update_expected_throttle_limit(bucket, num_items, doc_size)

        for bucket in read_bucket:
            self.expected_stats[bucket.name]["ru"] += \
                    self.bucket_util.calculate_units(key_size, doc_size) * num_items
            self.update_expected_throttle_limit(bucket, num_items, doc_size)
        self.validate_stats()

    def different_load(self, num_loop=1, num_write_bucket=1, num_read_bucket=0,
                       load="load_single_database"):
        start = self.num_items
        end = self.num_items + 3000
        self.load_data(create_start=start, create_end=end, create_perc=100)
        self.update_expected_stat(self.key_size, self.doc_size, 0,
                                  self.num_items, self.cluster.buckets)
        mutated = 0
        for loop in range(num_loop):
            # start = self.num_items
            # end = self.num_items + 100
            start = end
            end = start + 2000
            write_bucket = self.cluster.buckets[:1]
            if num_read_bucket > 1:
                read_bucket = self.cluster.buckets[1:]
            else:
                read_bucket = list()
            if load == "write_few_read_few":
                write_bucket = self.cluster.buckets[:num_write_bucket]
                read_bucket = self.cluster.buckets[num_read_bucket:]
                self.doc_size = 5000000
                self.load_data(create_start=start, create_end=end, create_perc=100, buckets=write_bucket)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, write_bucket)
                self.load_data(read_start=0, read_end=100, read_perc=100, buckets=read_bucket)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, read_bucket=read_bucket)
                mutated = 0
                self.load_data(update_start=0, update_end=100, update_perc=100, mutated=mutated, buckets=write_bucket)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, write_bucket)
                mutated += 1

            elif load == "diff_load_diff_database":
                # load only for specific buckets
                self.doc_size = 5000000
                self.load_data(create_start=start, create_end=end, create_perc=100, buckets=write_bucket)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, write_bucket)
                self.load_data(read_start=0, read_end=100, read_perc=100, buckets=read_bucket)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, read_bucket=read_bucket)
                self.doc_size = 500
                self.load_data(create_start=start, create_end=end, create_perc=100)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, self.cluster.buckets)

            elif load == "load_single_database":
                # load only for specific buckets
                self.doc_size = 900
                self.load_data(create_start=start, create_end=end, create_perc=100, buckets=write_bucket)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, write_bucket)
                self.load_data(update_start=0, update_end=100, update_perc=100, mutated=mutated, buckets=write_bucket)
                mutated += 1
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, write_bucket)

            elif load == "change_throttling_limit":
                throttling_limit = [-1, 100, 2000, 40000]
                self.bucket_util.set_throttle_limit(write_bucket,
                                                           throttling_limit=random.choice(throttling_limit))
                self.doc_size = 500000
                self.load_data(create_start=start, create_end=end, create_perc=100)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, self.cluster.buckets)
                self.bucket_util.set_throttle_limit(write_bucket, throttling_limit=500)
                start = end
                end = start + 100
                self.bucket_util.set_throttle_limit(write_bucket, throttling_limit=5000)
                self.doc_size = 500000
                self.load_data(create_start=start, create_end=end, create_perc=100)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, self.cluster.buckets)

            else:
                self.doc_size = 5000000
                self.load_data(create_start=start, create_end=end, create_perc=100)
                self.update_expected_stat(self.key_size, self.doc_size,
                                                      start, end, write_bucket)
            start = end
            end = start + 100

    def test_metering_database(self):
        """
        1. Loading initial buckets
        2. Start data loading to all buckets
        3. Create more buckets when data loading is running
        4. Delete the newly created database while intial load is still running
        :return:
        """
        self.db_name = "%s-testmetering" % self.db_name
        # validate initial throughput is 5000/3 = 1666
        for bucket in self.cluster.buckets:
            self.assertEqual(self.bucket_util.get_throttle_limit(bucket), 5000)

        # validate create, update, delete stat
        for op_type in ["create", "update", "delete"]:
            if op_type == "create":
                self.load_data(create_start=0, create_end=self.num_items, create_perc=100)
                self.update_expected_stat(self.key_size, self.doc_size,
                                          0, self.num_items, self.cluster.buckets)
            if op_type == "update":
                self.load_data(update_start=0, update_end=self.num_items, update_perc=100, mutated=1)
                self.update_expected_stat(self.key_size, self.doc_size,
                                          0, self.num_items, self.cluster.buckets)
            if op_type == "delete":
                self.load_data(delete_start=0, delete_end=self.num_items, delete_perc=100)
                # self.update_expected_stat(self.key_size, self.doc_size,
                #                           0, self.num_items, self.cluster.buckets)

    def test_diff_throttling_limit(self):
        self.test_single_bucket = self.input.param("test_single_bucket", False)
        self.different_throttle = self.input.param("different_throttle", False)
        self.load = self.input.param("load", "load_single_database")
        self.num_write_bucket = self.input.param("num_write_bucket", 1)
        self.num_read_bucket = self.input.param("num_read_bucket", 0)
        self.num_loop = self.input.param("num_loop", 1)
        # set different throtlle limits for the bucket
        if self.different_throttle:
            self.throttling_limits = [1000, -1, 10000, 2147483647, 100]
        else:
            self.throttling_limits = [self.bucket_throttling_limit]

        if self.test_single_bucket:
            bucket = self.cluster.buckets[0]
            for limit in self.throttling_limits:
                self.bucket_util.set_throttle_limit(bucket, limit)
                self.assertEqual(self.bucket_util.get_throttle_limit(bucket), limit)
                # perform load and validate stats
                self.different_load()
        else:
            for bucket in self.cluster.buckets:
                limit = random.choice(self.throttling_limits)
                self.bucket_util.set_throttle_limit(bucket, limit)
                self.assertEqual(self.bucket_util.get_throttle_limit(bucket), limit)
            self.different_load(self.num_loop, self.num_write_bucket, self.num_read_bucket, self.load)

    def test_limits_boundary_values(self):
        """ throttling limit = -1 to 2147483647
            storage limit = -1 to 2147483647
        """

        def check_error_msg(status, output, storagelimit=False):
            import json
            if status == False:
                content = json.loads(output)["errors"]
                if storagelimit:
                    actual_error = content["dataStorageLimit"]
                    expected_error = '"dataStorageLimit" must be an integer between -1 and 2147483647'
                else:
                    actual_error = content["dataThrottleLimit"]
                    expected_error = '"dataThrottleLimit" must be an integer between -1 and 2147483647'
                self.assertEqual(actual_error, expected_error)
            else:
                self.fail("expected to fail but passsed")

        bucket = self.cluster.buckets[0]
        for node in bucket.servers:
            rest_node = RestConnection(node)
            status, content = rest_node. \
                set_throttle_limit(bucket=bucket.name,
                                   throttle_limit=-2)
            check_error_msg(status, content)
            status, content = rest_node. \
                set_throttle_limit(bucket=bucket.name,
                                   throttle_limit=2147483648)
            check_error_msg(status, content)

            status, content = rest_node. \
                set_throttle_limit(bucket=bucket.name,
                                   storage_limit=-2)
            check_error_msg(status, content, True)
            status, content = rest_node. \
                set_throttle_limit(bucket=bucket.name,
                                   storage_limit=2147483648)
            check_error_msg(status, content, True)

            status, content = rest_node. \
                set_throttle_limit(bucket=bucket.name,
                                   throttle_limit=-2,
                                   storage_limit=-2)
            check_error_msg(status, content)
            check_error_msg(status, content, True)
            status, content = rest_node. \
                set_throttle_limit(bucket=bucket.name,
                                   throttle_limit=2147483648,
                                   storage_limit=2147483648)
            check_error_msg(status, content)
            check_error_msg(status, content, True)

    def test_zero_limits(self):
        bucket = self.cluster.buckets[0]
        end = 10
        for i in [1, 2]:
            if i == 1:
                self.bucket_util.set_throttle_limit(bucket, throttling_limit=0)
            else:
                self.bucket_util.set_throttle_limit(bucket, storage_limit=0)
            self.load_data(create_start=0, create_end=end)
            num_throttled, ru, wu = self.bucket_util.get_stat_from_metrics(bucket)
            if wu not in [0, 10]:
                self.fail("expected wu either as 0 or as %s but got %s" % (end, wu))