import logging

from Cb_constants import CbServer

log = logging.getLogger("x509")
from remote.remote_util import RemoteMachineShellConnection
from membase.api.rest_client import RestConnection
from membase.api import httplib2
import base64
import requests
import urllib
import random
import os
import copy
import subprocess


class ServerInfo():
    def __init__(self,
                 ip,
                 port,
                 ssh_username,
                 ssh_password,
                 memcached_port,
                 ssh_key=''):

        self.ip = ip
        self.ssh_username = ssh_username
        self.ssh_password = ssh_password
        self.port = port
        self.ssh_key = ssh_key
        self.memcached_port = memcached_port


class x509main:
    CHAINCERTFILE = 'chain.pem'
    NODECAKEYFILE = 'pkey.key'
    CACERTFILE = "root.crt"
    CAKEYFILE = "root.key"
    WININSTALLPATH = "C:/Program Files/Couchbase/Server/var/lib/couchbase/"
    LININSTALLPATH = "/opt/couchbase/var/lib/couchbase/"
    MACINSTALLPATH = "/Users/couchbase/Library/Application Support/Couchbase/var/lib/couchbase/"
    DOWNLOADPATH = "/tmp/"
    CACERTFILEPATH = "/tmp/newcerts" + str(random.randint(1,100)) + "/"
    CHAINFILEPATH = "inbox"
    GOCERTGENFILE = "gencert.go"
    INCORRECT_ROOT_CERT = "incorrect_root_cert.crt"
    SLAVE_HOST = ServerInfo('127.0.0.1', 22, 'root', 'couchbase',11210)
    CLIENT_CERT_AUTH_JSON = 'client_cert_auth1.json'
    CLIENT_CERT_AUTH_TEMPLATE = 'client_cert_config_template.txt'
    IP_ADDRESS = '172.16.1.174'
    KEY_FILE = CACERTFILEPATH + CAKEYFILE
    CERT_FILE = CACERTFILEPATH + CACERTFILE
    CLIENT_CERT_KEY = CACERTFILEPATH + IP_ADDRESS + ".key"
    CLIENT_CERT_PEM = CACERTFILEPATH + IP_ADDRESS + ".pem"
    SRC_CHAIN_FILE = CACERTFILEPATH + "long_chain" + IP_ADDRESS + ".pem"
    SECURITY_UTIL_PATH = "./couchbase_utils/security_utils/"

    def __init__(self,
                 host=None,
                 method='REST'):

        if host is not None:
            self.host = host
            self.install_path = self._get_install_path(self.host)
        self.slave_host = x509main.SLAVE_HOST

    def getLocalIPAddress(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('couchbase.com', 0))
        return s.getsockname()[0]
        '''
        status, ipAddress = commands.getstatusoutput("ifconfig en0 | grep 'inet addr:' | cut -d: -f2 |awk '{print $1}'")
        if '1' not in ipAddress:
            status, ipAddress = commands.getstatusoutput("ifconfig eth0 | grep  -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | awk '{print $2}'")
        return ipAddress
        '''

    def _generate_cert(self,servers,root_cn='Root\ Authority',type='go',encryption="",key_length=1024,client_ip=None,alt_names='default',dns=None,uri=None):
        shell = RemoteMachineShellConnection(self.slave_host)
        shell.execute_command("rm -rf " + x509main.CACERTFILEPATH)
        shell.execute_command("mkdir " + x509main.CACERTFILEPATH)
        
        if type == 'go':
            files = []
            cert_file = x509main.SECURITY_UTIL_PATH + x509main.GOCERTGENFILE
            output,error = shell.execute_command("go run " + cert_file + " -store-to=" + x509main.CACERTFILEPATH + "root -common-name="+root_cn)
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            output,error = shell.execute_command("go run " + cert_file + " -store-to=" + x509main.CACERTFILEPATH + "interm -sign-with=" + x509main.CACERTFILEPATH + "root -common-name=Intemediate\ Authority")
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            for server in servers:
                if "[" in server.ip:
                    server.ip = server.ip.replace("[", "").replace("]", "")
                output, error = shell.execute_command("go run " + cert_file + " -store-to=" + x509main.CACERTFILEPATH + server.ip + " -sign-with=" + x509main.CACERTFILEPATH + "interm -common-name=" + server.ip + " -final=true")
                log.info ('Output message is {0} and error message is {1}'.format(output,error))
                output, error = shell.execute_command("cat " + x509main.CACERTFILEPATH + server.ip + ".crt " + x509main.CACERTFILEPATH + "interm.crt  > " + " " + x509main.CACERTFILEPATH + "long_chain"+server.ip+".pem")
                log.info ('Output message is {0} and error message is {1}'.format(output,error))

            shell.execute_command("go run " + cert_file + " -store-to=" + x509main.CACERTFILEPATH + "incorrect_root_cert -common-name=Incorrect\ Authority")
        elif type == 'openssl':
            files = []
            v3_ca = x509main.SECURITY_UTIL_PATH + "v3_ca.ext"
            output, error = shell.execute_command("openssl genrsa " + encryption + " -out " + x509main.CACERTFILEPATH + "ca.key " + str(key_length))
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            output,error = shell.execute_command("openssl req -new -x509  -days 3650 -sha256 -key " + x509main.CACERTFILEPATH + "ca.key -out " + x509main.CACERTFILEPATH + "ca.pem -subj '/C=UA/O=My Company/CN=My Company Root CA'")
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            output, error = shell.execute_command("openssl genrsa " + encryption + " -out " + x509main.CACERTFILEPATH + "int.key " + str(key_length))
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            output, error = shell.execute_command("openssl req -new -key " + x509main.CACERTFILEPATH + "int.key -out " + x509main.CACERTFILEPATH + "int.csr -subj '/C=UA/O=My Company/CN=My Company Intermediate CA'")
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            output, error = shell.execute_command("openssl x509 -req -in " + x509main.CACERTFILEPATH + "int.csr -CA " + x509main.CACERTFILEPATH + "ca.pem -CAkey " + x509main.CACERTFILEPATH + "ca.key -CAcreateserial -CAserial " \
                            + x509main.CACERTFILEPATH + "rootCA.srl -extfile " + v3_ca + " -out " + x509main.CACERTFILEPATH +"int.pem -days 365 -sha256")
            log.info ('Output message is {0} and error message is {1}'.format(output,error))


            for server in servers:
                #check if the ip address is ipv6 raw ip address, remove [] brackets
                if "[" in server.ip:
                    server.ip = server.ip.replace("[", "").replace("]", "")
                from shutil import copyfile
                copyfile(x509main.SECURITY_UTIL_PATH + "clientconf.conf", x509main.SECURITY_UTIL_PATH + "clientconf3.conf")
                fin = open(x509main.SECURITY_UTIL_PATH + "clientconf3.conf", "a+")
                if ".com" in server.ip:
                    fin.write("\nDNS.0 = {0}".format(server.ip))
                else:
                    fin.write("\nIP.0 = {0}".format(server.ip.replace('[', '').replace(']', '')))
                fin.close()
                    
                import fileinput
                import sys
                for line in fileinput.input(x509main.SECURITY_UTIL_PATH + "clientconf3.conf", inplace=1):
                    if "ip_address" in line:
                        line = line.replace("ip_address",server.ip)
                    sys.stdout.write(line)
                        
    
                # print file contents for easy debugging
                fout = open(x509main.SECURITY_UTIL_PATH + "clientconf3.conf", "r")
                print fout.read()
                fout.close()
                
                
                output, error = shell.execute_command("openssl genrsa " + encryption + " -out " + x509main.CACERTFILEPATH +server.ip + ".key " + str(key_length))
                log.info ('Output message is {0} and error message is {1}'.format(output,error))
                
                output, error= shell.execute_command("openssl req -new -key " + x509main.CACERTFILEPATH + server.ip + ".key -out " + x509main.CACERTFILEPATH + server.ip + ".csr -config " + x509main.SECURITY_UTIL_PATH + "clientconf3.conf")
                log.info ('Output message is {0} and error message is {1}'.format(output,error))
                output, error = shell.execute_command("openssl x509 -req -in "+ x509main.CACERTFILEPATH + server.ip + ".csr -CA " + x509main.CACERTFILEPATH + "int.pem -CAkey " + \
                                x509main.CACERTFILEPATH + "int.key -CAcreateserial -CAserial " + x509main.CACERTFILEPATH + "intermediateCA.srl -out " + x509main.CACERTFILEPATH + server.ip + ".pem -days 365 -sha256 -extfile " + x509main.SECURITY_UTIL_PATH + "clientconf3.conf -extensions req_ext")
                
                log.info ('Output message is {0} and error message is {1}'.format(output, error))
                output, error = shell.execute_command("cat " + x509main.CACERTFILEPATH + server.ip + ".pem " + x509main.CACERTFILEPATH + "int.pem " + x509main.CACERTFILEPATH + "ca.pem > " + x509main.CACERTFILEPATH + "long_chain"+server.ip+".pem")
                log.info ('Output message is {0} and error message is {1}'.format(output,error))

            output, error = shell.execute_command("cp " + x509main.CACERTFILEPATH + "ca.pem " + x509main.CACERTFILEPATH + "root.crt")
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            
            os.remove(x509main.SECURITY_UTIL_PATH + "clientconf3.conf")
            #Check if client_ip is ipv6, remove []
            
            if "[" in client_ip:
                client_ip = client_ip.replace("[", "").replace("]", "")
            
            from shutil import copyfile
            copyfile(x509main.SECURITY_UTIL_PATH + "clientconf.conf", x509main.SECURITY_UTIL_PATH + "clientconf2.conf")
            fin = open(x509main.SECURITY_UTIL_PATH + "clientconf2.conf", "a+")
            if alt_names == 'default':
                fin.write("\nDNS.1 = us.cbadminbucket.com")
                fin.write("\nURI.1 = www.cbadminbucket.com")
            elif alt_names == 'non_default':
                if dns is not None:
                    dns = "\nDNS.1 = " + dns
                    fin.write(dns)
                if uri is not None:
                    uri = "\nURI.1 = " + dns
                    fin.write(uri)
            if ".com" in server.ip:
                fin.write("\nDNS.0 = {0}".format(server.ip))
            else:
                fin.write("\nIP.0 = {0}".format(server.ip.replace('[', '').replace(']', '')))
            fin.close()

            # print file contents for easy debugging
            fout = open(x509main.SECURITY_UTIL_PATH + "clientconf2.conf", "r")
            print fout.read()
            fout.close()
            
            #Generate Certificate for the client
            output, error = shell.execute_command("openssl genrsa " + encryption + " -out " + x509main.CACERTFILEPATH +client_ip + ".key " + str(key_length))
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            output, error= shell.execute_command("openssl req -new -key " + x509main.CACERTFILEPATH + client_ip + ".key -out " + x509main.CACERTFILEPATH + client_ip + ".csr -config "+ x509main.SECURITY_UTIL_PATH + "clientconf2.conf")
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            output, error = shell.execute_command("openssl x509 -req -in "+ x509main.CACERTFILEPATH + client_ip + ".csr -CA " + x509main.CACERTFILEPATH + "int.pem -CAkey " + \
                                x509main.CACERTFILEPATH + "int.key -CAcreateserial -CAserial " + x509main.CACERTFILEPATH + "intermediateCA.srl -out " + x509main.CACERTFILEPATH + client_ip + ".pem -days 365 -sha256 -extfile " + x509main.SECURITY_UTIL_PATH + "clientconf2.conf -extensions req_ext")
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            output, error = shell.execute_command("cat " + x509main.CACERTFILEPATH + client_ip + ".pem " + x509main.CACERTFILEPATH + "int.pem " + x509main.CACERTFILEPATH + "ca.pem > " + x509main.CACERTFILEPATH + "long_chain"+client_ip+".pem")
            log.info ('Output message is {0} and error message is {1}'.format(output,error))
            os.remove(x509main.SECURITY_UTIL_PATH + "clientconf2.conf")

    #Top level method for setup of nodes in the cluster
    def setup_cluster_nodes_ssl(self,servers=[],reload_cert=False):
        #Make a copy of the servers not to change self.servers
        copy_servers = copy.deepcopy(servers)
        #For each server in cluster, setup a node certificates, create inbox folders and copy + chain cert
        for server in copy_servers:
            x509main(server)._setup_node_certificates(reload_cert=reload_cert,host=server)
    
    #Create inbox folder and copy node cert and chain cert
    def _setup_node_certificates(self,chain_cert=True,node_key=True,reload_cert=True,host=None):
        if host == None:
            host = self.host
        self._create_inbox_folder(host)
        if host.ip.count(':') > 0 and host.ip.count(']') >0:
                # raw ipv6? enclose in square brackets
                host.ip = host.ip.replace('[', '').replace(']', '')
        src_chain_file = x509main.CACERTFILEPATH + "/long_chain" + host.ip + ".pem"
        dest_chain_file = self.install_path + x509main.CHAINFILEPATH + "/" + x509main.CHAINCERTFILE
        src_node_key = x509main.CACERTFILEPATH + "/" + host.ip + ".key"
        dest_node_key = self.install_path + x509main.CHAINFILEPATH + "/" + x509main.NODECAKEYFILE
        if chain_cert:
            self._copy_node_key_chain_cert(host, src_chain_file, dest_chain_file)
        if node_key:
            self._copy_node_key_chain_cert(host, src_node_key, dest_node_key)
        if reload_cert:
            status, content = self._reload_node_certificate(host)
            return status, content
    
    #Reload cert for self signed certificate
    def _reload_node_certificate(self,host):
        rest = RestConnection(host)
        api = rest.baseUrl + "node/controller/reloadCertificate"
        status, content, header = rest._http_request(api, 'POST', headers=self._create_rest_headers('Administrator','password'))
        #status, content, header = rest._http_request(api, 'POST')
        return status, content

    #Get the install path for different operating system
    def _get_install_path(self,host):
        shell = RemoteMachineShellConnection(host)
        os_type = shell.extract_remote_info().distribution_type
        log.info ("OS type is {0}".format(os_type))
        if os_type == 'windows':
            install_path = x509main.WININSTALLPATH
        elif os_type == 'Mac':
            install_path = x509main.MACINSTALLPATH
        else:
            install_path = x509main.LININSTALLPATH
        return install_path

    #create inbox folder for host
    def _create_inbox_folder(self,host):
        shell = RemoteMachineShellConnection(self.host)
        final_path = self.install_path + x509main.CHAINFILEPATH
        shell.create_directory(final_path)

    #delete all file inbox folder and remove inbox folder
    def _delete_inbox_folder(self):
        shell = RemoteMachineShellConnection(self.host)
        final_path = self.install_path + x509main.CHAINFILEPATH
        shell = RemoteMachineShellConnection(self.host)
        os_type = shell.extract_remote_info().distribution_type
        log.info ("OS type is {0}".format(os_type))
        shell.delete_file(final_path , "root.crt")
        shell.delete_file(final_path , "chain.pem")
        shell.delete_file(final_path , "pkey.key")
        if os_type == 'windows':
            final_path = '/cygdrive/c/Program\ Files/Couchbase/Server/var/lib/couchbase/inbox'
            shell.execute_command('rm -rf ' + final_path)
        else:
            shell.execute_command('rm -rf ' + final_path)

    #Function to simply copy from source to destination
    def _copy_node_key_chain_cert(self,host,src_path,dest_path):
        shell = RemoteMachineShellConnection(host)
        shell.copy_file_local_to_remote(src_path,dest_path)

    def _create_rest_headers(self,username="Administrator",password="password"):
        authorization = base64.encodestring('%s:%s' % (username,password))
        return {'Content-Type': 'application/json',
            'Authorization': 'Basic %s' % authorization,
            'Accept': '*/*'}
    
    #Function that will upload file via rest
    def _rest_upload_file(self,URL,file_path_name,username=None,password=None,curl=False,data_json=None):
        data  =  open(file_path_name, 'rb').read()
        status = None
        content = None
        if curl:
            cmd = "curl -v -d '%s' %s -u %s:%s -k"%(data_json,URL,username,password)
            log.info("Running command : {0}".format(cmd))
            content = subprocess.check_output(cmd, shell=True)
            return status, content
        if CbServer.use_https:
            rest = RestConnection(self.host)
            rest._http_request(URL, 'POST', headers=self._create_rest_headers(username,password), params=data)
        else:
            http = httplib2.Http()
            status, content = http.request(URL, 'POST', headers=self._create_rest_headers(username,password),body=data)
            log.info (" Status from rest file upload command is {0}".format(status))
            log.info (" Content from rest file upload command is {0}".format(content))
        return status, content

    #Upload Cluster or root cert
    def _upload_cluster_ca_certificate(self,username,password):
        rest = RestConnection(self.host)
        url = "controller/uploadClusterCA"
        api = rest.baseUrl + url
        self._rest_upload_file(api,x509main.CACERTFILEPATH + "/" + x509main.CACERTFILE,"Administrator",'password')
    
    #Upload security setting for client cert
    def _upload_cluster_ca_settings(self,username,password,data=None):
        temp = self.host
        rest = RestConnection(temp)
        url = "settings/clientCertAuth"
        api = rest.baseUrl + url
        status, content = self._rest_upload_file(api,x509main.CACERTFILEPATH + x509main.CLIENT_CERT_AUTH_JSON,"Administrator",'password',curl=True, data_json=data)
        log.info (" Status from upload of client cert settings is {0}".format(status))
        log.info (" Content from upload of client cert settings is {0}".format(content))
        return status, content

    '''
    Use requests module to execute rest api's
    Steps:
    1. Check if client_cert is set or not. This will define rest of the parameters for client certificates to set for connections
    2. check what is the verb required for rest api, get, post, put and delete for each rest api
    3. Call request with client certs, data that is passed for each request and headers for each request
    4. Return text of the response to the calling function
    Capture any exception in the code and return error
    '''
   
    def _validate_ssl_login(self, final_url=None, header=None, client_cert=False, verb='GET', data='', plain_curl=False, username='Administrator', password='password', host=None):
        if verb == 'GET' and plain_curl:
            r = requests.get(final_url, data=data)
            return r.status_code, r.text
        elif client_cert:
            try:
                if verb == 'GET':
                    r = requests.get(final_url,verify=x509main.CERT_FILE,cert=(x509main.CLIENT_CERT_PEM,x509main.CLIENT_CERT_KEY),data=data)
                elif verb == 'POST':
                    r = requests.post(final_url,verify=x509main.CERT_FILE,cert=(x509main.CLIENT_CERT_PEM,x509main.CLIENT_CERT_KEY),data=data)
                elif verb == 'PUT':
                    header = {'Content-type': 'Content-Type: application/json'}
                    r = requests.put(final_url,verify=x509main.CERT_FILE,cert=(x509main.CLIENT_CERT_PEM,x509main.CLIENT_CERT_KEY),data=data,headers=header)
                elif verb == 'DELETE':
                    header = {'Content-type': 'Content-Type: application/json'}
                    r = requests.delete(final_url, verify=x509main.CERT_FILE, cert=(x509main.CLIENT_CERT_PEM, x509main.CLIENT_CERT_KEY), headers=header)
                return r.status_code, r.text
            except Exception, ex:
                log.info ("into exception form validate_ssl_login with client cert")
                log.info (" Exception is {0}".format(ex))
                return 'error'
        else:
            try:
                r = requests.get("https://"+str(self.host.ip)+":18091",verify=x509main.CERT_FILE)
                if r.status_code == 200:
                    header = {'Content-type': 'application/x-www-form-urlencoded'}
                    params = urllib.urlencode({'user':'{0}'.format(username), 'password':'{0}'.format(password)})               
                    r = requests.post("https://"+str(self.host.ip)+":18091/uilogin",data=params,headers=header,verify=x509main.CERT_FILE)
                    return r.status_code
            except Exception, ex:
                log.info ("into exception form validate_ssl_login")
                log.info (" Exception is {0}".format(ex))
                return 'error'

    '''
    Call in curl requests to execute rest api's
    1. check for the verb that is GET or post or delete and decide which header to use
    2. check if the request is a simple curl to execute a rest api, no cert and no client auth
    3. Check if client cert is going to be used, in that case pass in the root cert, client key and cert
    4. Check the request is not for client cert, then pass in just the root cert
    5. Form the url, add url, header and ulr
    6. Add any data is there
    7. Execute the curl command
    retun the output of the curl command
    '''
    def _validate_curl(self,final_url=None,headers=None,client_cert=False,verb='GET',data='',plain_curl=False,username='Administrator',password='password'):
        
        if verb == 'GET':
            final_verb = 'curl -v'
        elif verb == 'POST':
            final_verb = 'curl -v -X POST'
        elif verb == 'DELETE':
            final_verb = 'curl -v -X DELETE'
        
        if plain_curl:
            main_url = final_verb
        elif client_cert:
            main_url = final_verb + " --cacert " + x509main.SRC_CHAIN_FILE + " --cert-type PEM --cert " + x509main.CLIENT_CERT_PEM + " --key-type PEM --key " + x509main.CLIENT_CERT_KEY
        else:
            main_url = final_verb + " --cacert " + x509main.CERT_FILE
         
        cmd = str(main_url) + " " + str(headers) + " " + str(final_url)
        if data is not None:
            cmd = cmd + " -d " + data
        log.info("Running command : {0}".format(cmd))
        output = subprocess.check_output(cmd, shell=True)
        return output

    '''
    Define what needs to be called for the authentication
    1. check if host is none, get it from the object
    2. check if the curl has to be plain execution, no cert at all else make it a https
    3. if the execution needs to be done via curl or via python requests
    Return the value of result.
    '''
    def _execute_command_clientcert(self,host=None,url=None,port=18091,headers=None,client_cert=False, curl=False,verb='GET',data=None,
                                    plain_curl=False, username='Administrator',password='password'):
        if host is None:
            host = self.host.ip
        
        if plain_curl:
            final_url = "http://" + str(host) + ":" + str(port) + str(url)
        else:
            final_url = "https://" + str(host) + ":" + str(port) + str(url)
        
        if curl:
            result = self._validate_curl(final_url, headers, client_cert, verb, data, plain_curl, username, password)
            return result
        else:
            status, result = self._validate_ssl_login(final_url, headers, client_cert, verb, data, plain_curl, username, password)
            return status, result
    
    #Get current root cert from the cluster
    def _get_cluster_ca_cert(self):
        rest = RestConnection(self.host)
        api = rest.baseUrl + "pools/default/certificate?extended=true"
        status, content, header = rest._http_request(api, 'GET')
        return status, content, header
    
    #Setup master node
    # 1. Upload Cluster cert i.e
    # 2. Setup other nodes for certificates
    # 3. Create the cert.json file which contains state, path, prefixes and delimeters
    # 4. Upload the cert.json file
    def setup_master(self, state=None, paths=None, prefixs=None, delimeters=None, user='Administrator',password='password'):
        copy_host = copy.deepcopy(self.host)
        x509main(copy_host)._upload_cluster_ca_certificate(user,password)
        x509main(copy_host)._setup_node_certificates()
        if state is not None:
            client_cert_json = self.write_client_cert_json_new(state, paths, prefixs, delimeters)
            x509main(copy_host)._upload_cluster_ca_settings(user,password,client_cert_json)
        
    #write a new config json file based on state, paths, perfixes and delimeters
    def write_client_cert_json_new(self, state, paths, prefixs, delimeters):
        template_path = x509main.SECURITY_UTIL_PATH + x509main.CLIENT_CERT_AUTH_TEMPLATE
        config_json = x509main.CACERTFILEPATH + x509main.CLIENT_CERT_AUTH_JSON
        target_file = open(config_json, 'w')
        source_file = open(template_path, 'r')
        client_cert= '{"state" : ' + "'" + state + "'" + ", 'prefixes' : [ "
        for line in source_file:
            for path, prefix, delimeter in zip(paths, prefixs, delimeters):
                line1 = line.replace("@2","'" + path + "'")
                line2 = line1.replace("@3","'" + prefix + "'")
                line3 = line2.replace("@4","'" + delimeter + "'")
                temp_client_cert = "{ " +  line3 + " },"
                client_cert = client_cert + temp_client_cert
        client_cert = client_cert.replace("'",'"')
        client_cert = client_cert.rstrip(',')
        client_cert = client_cert + " ]}" 
        log.info ("-- Log current config json file ---{0}".format(client_cert))
        target_file.write(client_cert)
        return client_cert
