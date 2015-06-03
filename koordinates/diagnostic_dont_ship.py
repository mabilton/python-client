import requests
import sys
import os
import uuid

import requests
import logging

import api
import koordexceptions
import chainclasstest

class TestClass(object):
    def __init__(self, v):
        self.value = v
    def makeme(self, v):
        self.the_list.append(str(uuid.uuid1()))
        return self.__class__(v)
class TestClassSub(TestClass):
    pass
class TestClassSubSub(TestClassSub):
    def __init__(self, v):
        self.value = v
        self.the_list = []


def main5():
    tc = TestClassSubSub("foo")
    tc2 = tc.makeme("bar")
    print("tc : {0}. value is {1}".format(id(tc), tc.value))
    print("tc2 : {0}. value is {1}".format(id(tc2), tc2.value))
    print("type of tc is : {0}".format(type(tc)))
    print("type of tc2 is : {0}".format(type(tc2)))
    if isinstance(tc, type(tc2)):
        print("tc and tc2 are instances of the same thing")
    if isinstance(tc2, type(tc)):
        print("tc2 and tc are instances of the same thing")
def getpass():
    '''
    Prompt user for Password until there is a Connection object
    '''
    import getpass

    if 'KPWD' in os.environ:
        return os.environ['KPWD']
    else:
        return(getpass.getpass('Please enter your Koordinates password: '))

def get_auth(u, p):
    """Creates an Authorisation object
    """
    return requests.auth.HTTPBasicAuth(u, p)

def target_url(id=1474):
    url_templates = {}
    url_templates['GET'] = {}
    url_templates['GET']['single'] = '''https://koordinates.com/services/api/v1/layers/{layer_id}/'''
    return url_templates['GET']['single'].format(layer_id=id)

def analyse_object_attributes(obj):
    for attribute in [a for a in dir(obj) if not a.startswith('__') and not callable(getattr(obj,a))]:
        print(attribute, " " , str(type(attribute)))

def main6(username):
    print("main 6 START +++++++++++++++++++++++++++++++++++++++++++++")
    #import pdb;pdb.set_trace()
    conn = api.Connection(username, getpass())
    for version in conn.version.get_list(layer_id=1474).execute_get_list():
        print(version.id, " ", version.created_at, " " , version.created_by)
    print("main 6 STOPx +++++++++++++++++++++++++++++++++++++++++++++")

def main7(username):
    print("main 7 START +++++++++++++++++++++++++++++++++++++++++++++")
    conn = api.Connection(username, getpass())
    conn.version.url="https://koordinates.com/services/api/v1/layers/1474/versions/4067/"
    conn.version.status = "ok"
    conn.version.created_at = "2012-05-09T02:11:27.020Z"
    conn.version.created_by=2879
    conn.version.reference=""
    conn.version.progress = 1 

    conn.version.insert(1474)
    print("main 7 STOP  +++++++++++++++++++++++++++++++++++++++++++++")

def main9(username):
    conn = api.Connection(username, getpass(), host="test.koordinates.com")
    test=True
    conn.version.import_version(999)
    test=False
def main8(username):
    print("main 8 START +++++++++++++++++++++++++++++++++++++++++++++")
    conn = api.Connection(username, getpass())
    conn.layer.name="Shea Test Layer 0"
    conn.layer.type = "layer"
    #... and so on
    #... until we get to this type of thing
    #... which requires a bit of thought as 
    #... so far we've avoided having "internal"
    #... class definitions and now we need a 
    #... Datasource class (although we do this dynamically
    #... for the GET's so probably OK)
    conn.layer.data.datasources = []
    conn.layer.data.datasources = [Datasource(id=999)]
    #... however that hightlight the primary
    #... issue which is this ... there's a danger
    #... I do this and then the only means
    #... of understanding that is wrong is when
    #... the POST hits the server
    conn.layer.badspellingofattributes = 0
    #Now k
    conn.layer.insert()
    print("main 8 STOP  +++++++++++++++++++++++++++++++++++++++++++++")

def make_list_string(lst):
    return "| ".join(lst)

def main10(username):
    conn = api.Connection(username, getpass())
    dic_types = {}
    last_id = None
    row_count = 0
    for the_data in conn.data.get_list().execute_get_list():
        row_count += 1
        last_id = the_data.id
        if the_data.type in dic_types:
            dic_types[the_data.type] += 1
        else:
            dic_types[the_data.type] = 1
    for k,v in dic_types.items():
        print("{} -> {}".format(k, v))
    print("row_count = {}".format(row_count))
    print("last id = {}".format(last_id))


def main4(username):
    #conn = api.Connection(username, getpass())
    #conn = api.Connection(username, getpass(), 'data.linz.govt.nz')
    conn = api.Connection(username, getpass())

    #for x in conn.layer.get_list().filter('Line of lowest astronomical tide for Australia').order_by('name').execute_get_list():
    # conn.layer.get_list().filter('Quattroshapes').order_by('name').execute_get_list():
    import pdb;pdb.set_trace()
    for the_layer in conn.layer.get_list().filter('Quattroshapes').order_by('name').execute_get_list():
        print(the_layer.tags)
        print(the_layer.collected_at)
        print(the_layer.id, " ", the_layer.name, " ", id(the_layer), make_list_string(the_layer.tags))

def main4A(username):
    conn = api.Connection(username, getpass())
    bln_first_one = True
    for the_layer in conn.layer.get_list().filter('Cadastral').order_by('name').execute_get_list():
        print(the_layer.id, " ", the_layer.name, " ", id(the_layer))
        if bln_first_one:
            analyse_object_attributes(the_layer)
            bln_first_one = False

    print("SET-" * 12)
    bln_first_one = True
    for the_set in conn.set.get_list().execute_get_list():
        print(the_set.id, " ", the_set.title )
        if bln_first_one:
            #analyse_object_attributes(the_set)
            bln_first_one = False
    # conn.layer.get_list().filter('Finland').order_by('name').execute_get_list()
    conn.layer.get(1474)
    print("[a] conn.layer analysis")
    analyse_object_attributes(conn.layer)
    print("[b0] conn.layer analysis")
    print(conn.layer.group)
    print("[b1] conn.layer analysis")
    print(type(conn.layer.group))
    print("[b2] conn.layer analysis")
    print(type(conn.layer))
    print("[c] conn.layer analysis")
    print(conn.layer.id)
    print("[d] conn.layer analysis")
    import datetime
    print("conn.layer.name ", conn.layer.name)
    if isinstance(conn.layer.name , datetime.date):
        print("conn.layer.name is a DATETIME instance")
    else:
        print("conn.layer.name is a NOT a DATETIME instance")
    print("conn.layer.data ", conn.layer.data)
    print("conn.layer.data.crs ", conn.layer.data.crs)
    print("conn.layer.data.fields[0] ", conn.layer.data.fields[0])
    for f in conn.layer.data.fields:
        print("f.type = ", f.type)
    print("conn.layer.data.fields[0].__dict__ ", conn.layer.data.fields[0].__dict__)
    print("conn.layer.data.fields[0].type ", conn.layer.data.fields[0].type)
    print("conn.layer.tags ", conn.layer.tags)
    print("conn.layer.created_at ", conn.layer.created_at)
    print("conn.layer.created_at.month ", conn.layer.created_at.month)
    if isinstance(conn.layer.created_at, datetime.date):
        print("conn.layer.created_at is a DATETIME instance")
    else:
        print("conn.layer.created_at is a NOT a DATETIME instance")

    print("conn.layer.collected_at " , conn.layer.collected_at)
    if isinstance(conn.layer.collected_at[0] , datetime.date):
        print("conn.layer.collected_at[0] is a DATETIME instance")
    else:
        print("conn.layer.collected_at[0] is a NOT a DATETIME instance")
    print("[e] conn.layer analysis")
    conn.layer.get(3994)
    print(conn.layer.name)
    print("[f] conn.layer analysis")

def main4B(username):
    conn = api.Connection(username, getpass())
    conn.layer.get(1474)
    print("")
    print(conn.layer.tags)
    print("")
    print(conn.layer.data.crs)
    print("")
    for f in conn.layer.data.fields:
        print(f.name)
    print("")
    print(conn.layer.collected_at)
    print("")
    print(conn.layer.id, " ", conn.layer.name, " ", id(conn.layer), make_list_string(conn.layer.tags))
    print("")

def main3():
    #cctold = chainclasstest.ChainClassTestOld([1,20,3,40])
    #print(cctold.order_by().filter_by())
    #print(cctold.filter_by().order_by())
    print()
    cct = chainclasstest.ChainClassTest([1,20,3,40],
                                        -999,
                                        '''https://koordinates.com/services/api/v1/layers/''')
    print("0" * 50)
    print(cct.url)
    print("1" * 50)
    cct.outputparsedurl()
    print("2" * 50)
    #cct.filter_by(name__contains='Wellington')
    print("3" * 50)
    #cct.filter_by(name__contains='Wellington').order_by()
    print("4" * 50)
    #cct.order_by().filter_by(name__contains='Wellington')
    cct.get_list().filter_by(name__contains='Wellington').order_by()
    print("5" * 50)
    cct.outputparsedurl()
    print("6" * 50)
    print(cct.url)
    print("7" * 50)
    '''
    print(cct)
    print(cct.order_by())
    print(cct.filter_by())
    '''
    '''
    print(cct.order_by().filter_by())
    '''
#def main2(username, url):
#    conn = api.Connection(username, getpass())
#    conn.layer.get(9999)
def main1(username, url, log):
    the_auth=get_auth(username, getpass())
    my_config = {'verbose': sys.stderr}

    #print(dir())
    #conn = api.Connection(username, getpass())
    #conn.layer.get(1474)


    # These two lines enable debugging at httplib level (requests->urllib3->http.client)
    # You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
    # The only thing missing will be the response.body which is not logged.
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1

    # You must initialize logging, otherwise you'll not see debug output.
    if log:
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True
    #
    req_resp = requests.get(url, auth=the_auth)
    #
    print("")
    print (type(req_resp.status_code))
    print("")
    if req_resp.status_code == "200":
        print("valid")
    else:
        print("invalid")
    print("")
    if req_resp.status_code == 200:
        print("valid")
    else:
        print("invalid")
    #
    #
    #

    print(dir())
def logger_tester(log):
    '''
    To test the koordinates logger
    '''
    if log:
        import logging
        logger = logging.getLogger(__name__)
        logging.basicConfig(filename='example.log',level=logging.DEBUG)
        logging.debug('This message should go to the log file')
        logging.info('So should this')
        logging.warning('And this, too')

def main():
    do_some_logging=True
    username = 'rshea@thecubagroup.com'
    url = target_url(id=1474)
    if False:
        main1(username, url, log=do_some_logging)
        main2(username, url)
        main3()
    main4B(username)
    if False:
        main4(username)
        main4A(username)
        main5()
        logger_tester(log=do_some_logging)
        main6(username)
        main7(username)
        main8(username)
        main9(username)
    main10(username)

if __name__ == "__main__":
    main()
