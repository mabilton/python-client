# -*- coding: utf-8 -*-

"""
koordinates.api
~~~~~~~~~~~~
This module implements the Koordinates API.

:copyright: (c) Koordinates .
:license: BSD, see LICENSE for more details.
"""

import abc
import logging
import json
import os
import pprint
import uuid
from datetime import datetime
try:
    from urllib.parse import urlencode
    from urllib.parse import urlsplit
    from urllib.parse import parse_qs
except ImportError:
    from urllib import urlencode
    from urlparse import urlsplit
    from urlparse import parse_qs

import dateutil.parser
import requests
import six

from .utils import (
    remove_empty_from_dict,
    dump_class_attributes_to_dict,
    make_date_list_from_string_list,
    make_date,
    make_date_if_possible,
    make_list_of_Datasources,
    make_list_of_Fields,
    make_list_of_Categories
)
from .exceptions import (
    KoordinatesException,
    KoordinatesValueException,
    InvalidAPIVersion,
    InvalidURL,
    NotAuthorised,
    UnexpectedServerResponse,
    OnlyOneFilterAllowed,
    FilterMustNotBeSpaces,
    NotAValidBasisForFiltration,
    OnlyOneOrderingAllowed,
    NotAValidBasisForOrdering,
    AttributeNameIsReserved,
    ServerTimeOut,
    RateLimitExceeded,
    ImportEncounteredUpdateConflict,
    PublishAlreadyStarted,
    InvalidPublicationResourceList
)
SUPPORTED_API_VERSIONS = ['v1', 'UNITTESTINGONLY']


logger = logging.getLogger(__name__)


class KoordinatesURLMixin(object):
    '''
    A Mixin to support URL operations
    '''
    URL_TEMPLATES = {
        'CONN': {
            'POST': {
                'publishmulti': '/publish/',
            },
        },
        'LAYER': {
            'GET': {
                'singleversion': '/layers/{layer_id}/versions/{version_id}/',
                'single': '/layers/{layer_id}/',
                'multi': '/layers/',
                'multidraft': '/layers/drafts/',
            },
            'POST': {
                'create': '/layers/',
                'update': '/layers/{layer_id}/import/',
            },
        },
        'SET': {
            'GET': {
                'single': '/sets/{set_id}/',
                'multi': '/sets/',
            },
        },
        'VERSION': {
            'GET': {
                'single': '/layers/{layer_id}/versions/{version_id}/',
                'multi': '/layers/{layer_id}/versions/',
            },
            'POST': {
                'import': '/layers/{layer_id}/versions/{version_id}/import/',
                'publish': '/layers/{layer_id}/versions/{version_id}/publish/',
            },
        },
        'DATA': {
            'GET': {
                'multi': '/data/',
                'single': '/data/{data_id}',
            },
        },
        'TABLE': {
            'GET': {
                'singleversion': '/tables/{table_id}/versions/{version_id}/',
            },
        },
        'PUBLISH': {
            'GET': {
                'single': '/publish/{publish_id}/',
                'multi': '/publish/',
            },
            'DELETE': {
                'single': '/publish/{publish_id}/',
            }
        },
    }

    def get_url(self, datatype, verb, urltype, kwargs={}):
        """Returns a fully formed url

        :param datatype: a string identifying the data the url will access .
        :param verb: the HTTP verb needed for use with the url .
        :param urltype: an adjective used to the nature of the request .
        :param \*\*kwargs: Optional arguments that allows override of the hostname or api version to be embedded in teh resulting url.
        :return: string
        :rtype: A fully formed url.
        """
        if "hostname" not in kwargs:
            try:
                kwargs['hostname'] = self._parent.host
            except AttributeError:
                # We need to cater for when `get_url` is
                # invoked from a method on the `Connection`
                # object itself
                kwargs['hostname'] = self.host
        if "api_version" not in kwargs:
            try:
                kwargs['api_version'] = self._parent.api_version
            except AttributeError:
                # We need to cater for when `get_url` is
                # invoked from a method on the `Connection`
                # object itself
                kwargs['api_version'] = self.api_version

        url = "https://{hostname}/services/api/{api_version}"
        url += self.URL_TEMPLATES[datatype][verb][urltype]
        return url.format(**kwargs)

class KoordinatesObjectMixin(object):
    '''
    A Mixin providing the generic aspects of server interations
    for subclasses
    '''
    __metaclass__ = abc.ABCMeta

    def create(self, target_url):
        """Creates a object based on contents value of `id`.

        """

        json_headers = {'Content-type': 'application/json', 'Accept': '*/*'}
        json_body = dump_class_attributes_to_dict(self)
        logger.debug('First pass JSON body for create follows')
        logger.debug(pprint.pformat(json_body))

        json_body = remove_empty_from_dict(json_body)
        logger.debug('Second pass JSON body for create follows')
        logger.debug(pprint.pformat(json_body))

        self._raw_response = requests.post(target_url,
                                           json=json_body,
                                           headers=json_headers,
                                           auth=self._parent.get_auth())

        if self._raw_response.status_code == 201:
            logger.debug('Return value from successful instance create follows')
            logger.debug(pprint.pformat(self._raw_response.text))

            good_layer_dict = self._raw_response.json()

            self.created_at = self.__make_date_if_possible(good_layer_dict['created_at'])
            self.created_by = good_layer_dict['created_by']
            self.url = good_layer_dict['url']
        elif self._raw_response.status_code == 401:
            raise NotAuthorised
        elif self._raw_response.status_code == 404:
            raise InvalidURL
        elif self._raw_response.status_code == 429:
            raise RateLimitExceeded
        elif self._raw_response.status_code == 504:
            raise ServerTimeOut
        else:
            raise UnexpectedServerResponse(self._raw_response.status_code, " ", self._raw_response.text)


    @abc.abstractmethod
    def get(self, id, target_url, dynamic_build = False):
        """Fetches a single object determined by the value of `id`.

        :param id: ID for the new object.
        :param target_url: the url on which to do the GET .
        :param dynamic_build: When True the instance hierarchy arising from the
                              JSON returned is automatically build. When False
                              control is handed back to the calling subclass to
                              build the instance hierarchy based on pre-defined
                              classes.

                              An example of `dynamic_build` being False is that
                              the `Layer` class will have the JSON arising from
                              GET returned to it and will then follow processing
                              defined in `Layer.get` to create an instance of
                              `Layer` from the JSON returned.

                              NB: In later versions this flag will be withdrawn
                              and all processing will be done as if `dynamic_build`
                              was False.
        """

        self._raw_response = requests.get(target_url,
                                          auth=self._parent.get_auth())

        if self._raw_response.status_code == 200:
            # convert JSON to dict
            dic_json = json.loads(self._raw_response.text)
            # itererte over resulting dict
            if dynamic_build:
                # Build an instance hierarchy based on an introspection of the
                # JSON returned.
                for dict_key, dict_element_value in dic_json.items():
                    if isinstance(dict_element_value, dict):
                        # build dynamically defined class instances (nested
                        # if necessary) in order to model associative arrays
                        att_value = self._class_builder_from_dict(dic_json[dict_key], dict_key)
                    elif isinstance(dict_element_value, list):
                        att_value = self.__class_builder_from_sequence(dic_json[dict_key])
                    elif isinstance(dict_element_value, tuple):
                        # Don't believe the json.loads will ever create Tuples and supporting
                        # them later is costly so for the moment we just give up at this point
                        raise NotImplementedError("JSON that creates Tuples is not currently supported")
                    else:
                        # Allocate value to attribute directly
                        att_value = dict_element_value
                    self.__create_attribute(dict_key, att_value)
            else:
                # Return a representation of the JSON returned to calling subclass
                # method and allow that method to build the resulting instance
                # hierarchy
                return dic_json
        elif self._raw_response.status_code == 401:
            raise NotAuthorised
        elif self._raw_response.status_code == 404:
            raise InvalidURL(target_url)
        elif self._raw_response.status_code == 429:
            raise RateLimitExceeded
        elif self._raw_response.status_code == 504:
            raise ServerTimeOut
        else:
            raise UnexpectedServerResponse

    def __specify_page(self, value):
        pass

    def filter(self, value):
        if self._filtering_applied:
            raise OnlyOneFilterAllowed

        # Eventually this check will be a good deal more sophisticated
        # so it's here in its current form to some degree as a placeholder
        if value.isspace():
            raise FilterMustNotBeSpaces()

        self.add_query_component("q", value)
        self._filtering_applied = True
        return self

    def order_by(self, sort_key):
        if self._ordering_applied:
            raise OnlyOneOrderingAllowed
        if sort_key not in self._attribute_sort_candidates:
            raise NotAValidBasisForOrdering(sort_key)

        self.add_query_component("sort", sort_key)
        self._ordering_applied = True
        return self

    def add_query_component(self, argname, argvalue):

        # parse original string url
        url_data = urlsplit(self._url)

        # parse original query-string
        qs_data = parse_qs(url_data.query)

        # manipulate the query-string
        qs_data[argname] = [argvalue]

        # get the url with modified query-string
        self._url = url_data._replace(query=urlencode(qs_data, True)).geturl()

    def execute_get_list(self, dynamic_build = False):
        """Fetches zero, one or more objects .

        :param dynamic_build: When True the instance hierarchy arising from the
                              JSON returned is automatically build. When False
                              control is handed back to the calling subclass to
                              build the instance hierarchy based on pre-defined
                              classes.

                              An example of `dynamic_build` being False is that
                              the `Layer` class will have the JSON arising from
                              GET returned to it and will then follow processing
                              defined in `Layer.get` to create an instance of
                              `Layer` from the JSON returned.

                              NB: In later versions this flag will be withdrawn
                              and all processing will be done as if `dynamic_build`
                              was False.
        """
        self._list_of_response_dicts = []
        self._next_page_number = 1
        self.add_query_component("page", self._next_page_number)
        self.__execute_get_list_no_generator()
        for list_of_responses in self._list_of_response_dicts:
            for response in list_of_responses:
                if dynamic_build:
                    this_object = self.__class__(self._parent)
                    for key, value in response.items():
                        setattr(this_object, key, value)
                    yield this_object
                else:
                    yield response
            if self._link_to_next_in_list:
                self.__execute_get_list_no_generator(target_url=self._link_to_next_in_list)

    def __execute_get_list_no_generator(self,
                                        target_url=None):

        if not target_url:
            target_url = self._url
        self._url = ""
        self._ordering_applied = False
        self._filtering_applied = False
        self._raw_response = requests.get(target_url,
                                          auth=self._parent.get_auth())

        if self._raw_response.status_code == 200:
            # If only row is returned the JSON corresponds to a single dict,
            # if more than one row is returned the JSON corresponds to a list
            # of dicts. To make life simpler in the case of a single dict we
            # coerce the single dict into a list
            if isinstance(self._raw_response.json(), dict):
                response_json = [self._raw_response.json()]
            else:
                response_json = self._raw_response.json()

            self._list_of_response_dicts.append(response_json)
            if 'page-next' in self._raw_response.links:
                self._link_to_next_in_list = self._raw_response.links['page-next']['url']
            else:
                self._link_to_next_in_list = None
        elif self._raw_response.status_code == 401:
            raise NotAuthorised
        elif self._raw_response.status_code == 404:
            raise InvalidURL
        elif self._raw_response.status_code == 429:
            raise RateLimitExceeded
        elif self._raw_response.status_code == 504:
            raise ServerTimeOut
        else:
            raise UnexpectedServerResponse

    def __create_attribute(self, att_name, att_value):
        if att_name in self._attribute_reserved_names:
            errmsg = """The name '{attname}' is not able to be used """ \
                     """an attribute name for the class '{classname}' """ \
                     """as it appears in the '_attribute_reserved_names' """ \
                     """list""".format(attname=att_name, classname=type(self).__name__)
            raise AttributeNameIsReserved(errmsg)

        if isinstance(att_value, list):
            att_value = [self.__make_date_if_possible(v) for v in att_value]
        else:
            att_value = self.__make_date_if_possible(att_value)

        setattr(self, att_name, att_value)

    def __make_date(self, value):
        '''
        `value` should either be a string
        parseable as a date/time; an empty
        string; or None

        Return either a `DateTime` corresponding
        to `value` or an empty String
        '''
        if value == "" or value is None:
            return ""
        else:
            return dateutil.parser.parse(value)


    def __make_date_if_possible(self, value):
        '''
        Try converting the value to a date
        and if that doesn't work then just
        return the value was it was passed
        in.
        '''
        try:
            out = dateutil.parser.parse(value)
        except ValueError:
            out = value
        except AttributeError:
            out = value

        return out

    def __class_builder_from_sequence(self, the_seq):
        '''__class_builder supports the dynamic creation of
        object attributes in response to JSON returned from the
        server.

        Where a JSON blob returned from the server (itself an
        associative array) includes nested associative arrays
        we need to create a class that corresponds to the contents
        of that array, create an instance of the class and then
        make that instance an attribute of our container class,
        for instance, a Layer
        '''
        seq_out = []
        for seq_element in the_seq:
            if isinstance(seq_element, list) or isinstance(seq_element, tuple):
                seq_out.append(self.__class_builder_from_sequence(seq_element))
            elif isinstance(seq_element, dict):
                seq_out.append(self._class_builder_from_dict(seq_element, str(uuid.uuid1())))
            else:
                seq_out.append(self.__make_date_if_possible(seq_element))
        return seq_out

    def _class_builder_from_dict(self, the_dic, the_name):
        '''_class_builder_from_dict supports the dynamic creation of
        object attributes in response to JSON returned from the
        server.

        Where a JSON blob returned from the server (itself an
        associative array) includes nested associative arrays
        we need to create a class that corresponds to the contents
        of that array, create an instance of the class and then
        make that instance an attribute of our container class,
        for instance, a Layer
        '''
        dic_out = {}
        for dict_key, dict_key_value in the_dic.items():
            if isinstance(dict_key_value, dict):
                dic_out[dict_key] = self._class_builder_from_dict(dict_key_value, dict_key)
            if isinstance(dict_key_value, list) or isinstance(dict_key_value, tuple):
                dic_out[dict_key] = self.__class_builder_from_sequence(dict_key_value)
            else:
                dic_out[dict_key] = self.__make_date_if_possible(dict_key_value)
        return type(str(the_name.title()), (object,), dic_out)



class PublishRequest(KoordinatesURLMixin):
    """
    Defines the nature of a multiple item Publish request
    """
    def __init__(self, layers=[], tables=[], kwargs={}):
        """
        `layers`: a list of dicts of the form {'layer_id':n, 'version_id':m}
        `tables`: a list of dicts of the form {'table_id':n, 'version_id':m}
        """

        assert type(layers) is list,\
            "The 'layers' argument must be a list"
        assert type(tables) is list,\
            "The 'tables' argument must be a list"

        self.layers = layers
        self.tables = tables
        if "hostname" in kwargs:
            self.hostname = kwargs['hostname']
        else:
            self.hostname = None
        if "api_version" in kwargs:
            self.api_version = kwargs['api_version']
        else:
            self.api_version = None

    def add_table_to_publish(self, table_id, version_id):
        self.tables.append({'table_id': table_id, 'version_id': version_id})

    def add_layer_to_publish(self, layer_id, version_id):
        self.layers.append({'layer_id': layer_id, 'version_id': version_id})

    def validate(self):
        '''
        Validates that the resources specified for Publication are in the
        correct format.
        '''

        self.good_layers()
        self.good_tables()

    def good_tables(self):
        '''
        Validates a list of tables ids and a corresponding version id which will be
        used to specify the tables to be published
        '''
        return self.__good_resource_specifications(self.tables, 'table')

    def good_layers(self):
        '''
        Validates a list of layers ids and a corresponding version id which will be
        used to specify the layers to be published
        '''
        return self.__good_resource_specifications(self.layers, 'layer')

    def __good_resource_specifications(self, lst_resources, resource_name):
        '''
        Validates a list of resource ids which will be used to specify the resources
        to be published

        `lst_resource`: A list of dictionaries which correspond to the resources
                        to be published. Each dictionary must have the keys: X_id
                        (where 'X' is 'table', 'layer', etc) ; and 'version_id'.
                        The associated elements should the unique identifiers of
                        the table/version or layer/version which is to be published

        `resource_name`: A string which corresponds to the attribute of this class
                        which is being validated. Valid values are 'layers' and 'tables'

        '''

        if type(lst_resources) is list:
            if len(lst_resources) == 0:
                pass
            else:
                for resource_dict in lst_resources:
                    if type(resource_dict) is dict:
                        if (resource_name + '_id') in resource_dict and 'version_id' in resource_dict:
                            pass
                        else:
                            raise InvalidPublicationResourceList(
                                "{resname} must be list of dicts. "
                                "Each dict must have the keys "
                                "{resname}_id and version_id".format(resname=resource_name))
                    else:
                        raise InvalidPublicationResourceList(
                            "Each element of {resname} must be a dict. "
                            .format(resname=resource_name))
        else:
            raise InvalidPublicationResourceList(
                "{resname} must be list of dicts. "
                "Each dict must have the keys "
                "{resname}_id and version_id".format(resname=resource_name))


class Connection(KoordinatesURLMixin):
    """
    A `Connection` is used to define the host and api-version which the user
    wants to connect to. The user identity is also defined when `Connection`
    is instantiated.
    """

    def __init__(self, username, pwd=None, host='koordinates.com',
                 api_version='v1', activate_logging=True):
        '''
        :param username: the username under which to make the connections
        :param pwd: the password under which to make the connections
        :param host: the host to connect to
        :param api_version: the version of teh api to connect to
        :param activate_logging: When True then logging to timestamped log files is activated

        '''
        if activate_logging:
            client_logfile_name = "koordinates-client-{}.log"\
                                  .format(datetime.now().strftime('%Y%m%dT%H%M%S'))
            logging.basicConfig(filename=client_logfile_name,
                                level=logging.DEBUG,
                                format='%(asctime)s %(levelname)s %(module)s %(message)s')

        logger.debug('Initializing Connection object')

        if api_version not in SUPPORTED_API_VERSIONS:
            #raise InvalidAPIVersion
            raise InvalidAPIVersion
        else:
            self.api_version = api_version

        self.host = host

        self.username = username
        if pwd:
            self.pwd = pwd
        else:
            self.pwd = os.environ['KPWD']

        self.layer = Layer(self)
        self.set = Set(self)
        self.version = Version(self)
        self.data = KData(self)
        self.publish = Publish(self)

        super(self.__class__, self).__init__()

    def get_auth(self):
        """Creates an Authorisation object based on the
        instance data of the `Connection` instance.


        :return: a `requests.auth.HTTPBasicAuth` instance
        """
        return requests.auth.HTTPBasicAuth(self.username,
                                           self.pwd)

    def build_multi_publish_json(self, pub_request, publish_strategy, error_strategy):
        '''
        Build a JSON body suitable for the multi-resource
        publishing

        :param pub_request: a PublishRequest instance .
        :param pub_strategy: a string defining the publish_strategy.
        :param error_strategy: a string defining the error_strategy.

        :return: a dictionary which corresponds to the body required\
                when doing a `Connection.multipublish` of resources.

        '''

        pub_request.validate()

        dic_out = {}
        if publish_strategy:
            dic_out['publish_strategy'] = publish_strategy
        if error_strategy:
            dic_out['error_strategy'] = error_strategy

        lst_items = []

        for table_resource_dict in pub_request.tables:
            table_resource_dict['hostname'] = self.host
            table_resource_dict['api_version'] = self.api_version
            target_url = self.get_url('TABLE', 'GET', 'singleversion', table_resource_dict)
            lst_items.append(target_url)

        for layer_resource_dict in pub_request.layers:
            layer_resource_dict['hostname'] = self.host
            layer_resource_dict['api_version'] = self.api_version
            target_url = self.get_url('LAYER', 'GET', 'singleversion', layer_resource_dict)
            lst_items.append(target_url)

        dic_out['items'] = lst_items

        return dic_out

    def request(self, method, url, *args, **kwargs):
        # headers = {
        #     'Content-type': 'application/json',
        #     'Accept': '*/*',
        # }
        r = requests.request(method, url, auth=self.get_auth(), *args, **kwargs)
        return r

    def multi_publish(self, pub_request, publish_strategy=None, error_strategy=None):
        """Publishes a set of items, potentially a mixture of Layers and Tables

        :param pub_request: A `PublishRequest' object specifying what resources are to be published
        :param pub_strategy: A string defining the publish_strategy. One of: `"individual"`, `"together"`. Default = `"together"`
        :param error_strategy: a string defining the error_strategy. One of: `"abort"`, `"ignore"`. Default = `"abort"`

        :return: a dictionary which corresponds to the body required\
                when doing a `Connection.multipublish` of resources.

        """
        assert type(pub_request) is PublishRequest,\
            "The 'pub_request' argument must be a PublishRequest instance"
        assert publish_strategy in ["individual", "together", None],\
            "The 'publish_strategy' value must be None or 'individual' or 'together'"
        assert error_strategy in ["abort", "ignore", None],\
            "The 'error_strategy' value must be None or 'abort' or 'ignore'"

        dic_args = {}
        if pub_request.hostname:
            dic_args = {'hostname': pub_request.hostname}
        if pub_request.api_version:
            dic_args = {'api_version': pub_request.api_version}

        target_url = self.get_url('CONN', 'POST', 'publishmulti', dic_args)
        dic_body = self.build_multi_publish_json(pub_request, publish_strategy, error_strategy)
        r = self.request('POST', target_url, json=dic_body)

        if r.status_code == 201:
            # Success !
            pass
        elif r.status_code == 404:
            # The resource specificed in the URL could not be found
            raise InvalidURL
        elif r.status_code == 409:
            # Indicates that the request could not be processed because
            # of conflict in the request, such as an edit conflict in
            # the case of multiple updates
            raise ImportEncounteredUpdateConflict
        else:
            raise UnexpectedServerResponse


class Publish(KoordinatesObjectMixin, KoordinatesURLMixin):
    '''A Publish

    TODO: Description of what a `Publish` is

    '''
    '''
    "id": 2054,
    "url": "https://test.koordinates.com/services/api/v1/publish/2054/",
    "state": "completed",
    "created_at": "2015-06-08T03:40:40.368Z",
    "created_by": {"id": 18504, "url": "https://test.koordinates.com/services/api/v1/users/18504/", "first_name": "Richard", "last_name": "Shea", "country": "NZ"},
    "error_strategy": "abort",
    "publish_strategy": "together",
    "publish_at": null,
    "items": ["https://test.koordinates.com/services/api/v1/layers/8092/versions/9822/"]
    '''
    def __init__(self,
                 parent=None,
                 id=None,
                 url=None,
                 state=None,
                 created_at=None,
                 created_by=None,
                 error_strategy=None,
                 publish_strategy=None,
                 publish_at=None,
                 items=None):


        self._parent = parent
        self._url = None
        self._id = id

        self._raw_response = None
        self._list_of_response_dicts = []
        self._link_to_next_in_list = ""
        self._next_page_number = 1
        self._attribute_sort_candidates = ['name']
        self._attribute_filter_candidates = ['name']
        # An attribute may not be created automatically
        # due to JSON returned from the server with any
        # names which appear in the list
        # _attribute_reserved_names
        self._attribute_reserved_names = []

        self._initialize_named_attributes(id,
                                         url,
                                         state,
                                         created_at,
                                         created_by,
                                         error_strategy,
                                         publish_strategy,
                                         publish_at,
                                         items)

        super(self.__class__, self).__init__()

    def _initialize_named_attributes(self,
                                     id,
                                     url,
                                     state,
                                     created_at,
                                     created_by,
                                     error_strategy,
                                     publish_strategy,
                                     publish_at,
                                     items):
        '''
        `_initialize_named_attributes` initializes those
        attributes of `Publish` which are not prefixed by an
        underbar. Such attributes are named so as to indicate
        that they are, in terms of the API, "real" attributes
        of a `Publish`. That is to say an attribute which is returned
        from the server when a given `Publish` is requested. Other
        attributes, such as `_attribute_reserved_names` have leading
        underbar to indicate they are not derived from data returned
        from the server

        '''

        self.id = id
        self.url = url
        self.state = state
        self.created_at = created_at
        self.created_by = created_by if created_by else Createdby()
        self.error_strategy = error_strategy
        self.publish_strategy = publish_strategy
        self.publish_at = publish_at
        self.items = items if items else []


    @classmethod
    def from_dict(cls, dict_publish):
        '''Initialize Group from a dict.

        la = Group.from_dict(a_dict)


        '''
        if dict_publish:
            the_publish = cls(None,
                              dict_publish.get("id", None),
                              dict_publish.get("url", None),
                              dict_publish.get("state", None),
                              make_date(dict_publish.get("created_at", None)),
                              Createdby.from_dict(dict_publish.get("created_by", None)),
                              dict_publish.get("error_strategy",None),
                              dict_publish.get("publish_strategy", None),
                              make_date(dict_publish.get("publish_at", None)),
                              dict_publish.get("items", []))
        else:
            the_publish = cls()

        return the_publish

    def execute_get_list(self):
        """Fetches zero, one or more Publishs .

        :param dynamic_build: When True the instance hierarchy arising from the
                              JSON returned is automatically build. When False
                              control is handed back to the calling subclass to
                              build the instance hierarchy based on pre-defined
                              classes.

                              An example of `dynamic_build` being False is that
                              the `Publish` class will have the JSON arising from
                              GET returned to it and will then follow processing
                              defined in `Publish.get` to create an instance of
                              `Publish` from the JSON returned.

                              NB: In later versions this flag will be withdrawn
                              and all processing will be done as if `dynamic_build`
                              was False.
        """
        for dic_publish_as_json in super(self.__class__, self).execute_get_list():
            the_publish =  Publish.from_dict(dic_publish_as_json)
            yield the_publish

    def get(self, id):
        """Fetches a `Publish` determined by the value of `id`.

        :param id: ID for the new :class:`Publish` object.
        """

        target_url = self.get_url('PUBLISH', 'GET', 'single', {'publish_id': id})
        super(self.__class__, self).get(id, target_url)

    def get_list(self):
        """Fetches a set of layers
        """
        target_url = self.get_url('PUBLISH', 'GET', 'multi')
        self._url = target_url
        return self

    def cancel(self):
        """Cancel a pending publish task
        """
        assert type(self.id) is int,\
            "The 'id' attribute is not an integer, it should be - have you fetched a publish record ?"

        target_url = self.get_url('PUBLISH', 'DELETE', 'single', {'publish_id': self.id})
        json_headers = {'Content-type': 'application/json', 'Accept': '*/*'}
        self._raw_response = requests.delete(target_url,
                                           headers=json_headers,
                                           auth=self._parent.get_auth())

        if self._raw_response.status_code == 202:
            # Success !
            pass
        elif self._raw_response.status_code == 409:
            # Indicates that the publish couldn't be cancelled as the
            # Publish process has already started
            raise PublishAlreadyStarted
        else:
            raise UnexpectedServerResponse


class KData(KoordinatesObjectMixin, KoordinatesURLMixin):
    '''A Data

    TODO: Description of what a `Data` is

    '''
    def __init__(self, parent, id=None):
        logger.info('Initializing KData object')
        self._parent = parent
        self._url = None
        self._id = id

        self._raw_response = None
        self._list_of_response_dicts = []
        self._link_to_next_in_list = ""
        self._next_page_number = 1
        self._attribute_sort_candidates = ['name']
        self._attribute_filter_candidates = ['name']
        # An attribute may not be created automatically
        # due to JSON returned from the server with any
        # names which appear in the list
        # _attribute_reserved_names
        self._attribute_reserved_names = []
        super(self.__class__, self).__init__()

    def get_list(self):
        """Fetches a set of sets
        """
        target_url = self.get_url('DATA', 'GET', 'multi')
        self._url = target_url
        return self

    def get(self, id):
        """Fetches a `KData` determined by the value of `id`.

        :param id: ID for the new :class:`KData` object.

        target_url = self.get_url('DATA', 'GET', 'single', {'data_id': id})
        super(self.__class__, self).get(id, target_url)
        """
        pass

class Set(KoordinatesObjectMixin, KoordinatesURLMixin):
    '''A Set

    TODO: Description of what a `Set` is

    '''
    def __init__(self,
                 parent=None,
                 id=None,
                 title=None,
                 description=None,
                 description_html=None,
                 categories=None,
                 tags=None,
                 group=None,
                 items=None,
                 url=None,
                 url_html=None,
                 metadata=None,
                 created_at=None):

        logger.info('Initializing Set object')
        self._parent = parent
        self._url = None
        self._id = id

        self._raw_response = None
        self._list_of_response_dicts = []
        self._link_to_next_in_list = ""
        self._next_page_number = 1
        self._attribute_sort_candidates = ['name']
        self._attribute_filter_candidates = ['name']
        # An attribute may not be created automatically
        # due to JSON returned from the server with any
        # names which appear in the list
        # _attribute_reserved_names
        self._attribute_reserved_names = []

        self._initialize_named_attributes(id,
                                          title,
                                          description,
                                          description_html,
                                          categories,
                                          tags,
                                          group,
                                          items,
                                          url,
                                          url_html,
                                          metadata,
                                          created_at)

        super(self.__class__, self).__init__()


    def _initialize_named_attributes(self,
                                     id,
                                     title,
                                     description,
                                     description_html,
                                     categories,
                                     tags,
                                     group,
                                     items,
                                     url,
                                     url_html,
                                     metadata,
                                     created_at):
        '''
        `_initialize_named_attributes` initializes those
        attributes of `Set` which are not prefixed by an
        underbar. Such attributes are named so as to indicate
        that they are, in terms of the API, "real" attributes
        of a `Set`. That is to say an attribute which is returned
        from the server when a given `Set` is requested. Other
        attributes, such as `_attribute_reserved_names` have leading
        underbar to indicate they are not derived from data returned
        from the server
        '''
        '''
        "id": 933,
        "title": "Ultra Fast Broadband Initiative Coverage",
        "description": "",
        "description_html": "",
        "categories": [],
        "tags": [],
        "group": {"id": 141, "url": "https://koordinates.com/services/api/v1/groups/141/", "name": "New Zealand Broadband Map", "country": "NZ"},
        "items": ["https://koordinates.com/services/api/v1/layers/4226/", "https://koordinates.com/services/api/v1/layers/4228/", "https://koordinates.com/services/api/v1/layers/4227/", "https://koordinates.com/services/api/v1/layers/4061/", "https://koordinates.com/services/api/v1/layers/4147/", "https://koordinates.com/services/api/v1/layers/4148/"],
        "url": "https://koordinates.com/services/api/v1/sets/933/",
        "url_html": "https://koordinates.com/set/933-ultra-fast-broadband-initiative-coverage/",
        "metadata": null,
        "created_at": "2012-03-21T21:49:51.420Z"
        '''
        self.id = id
        self.title = title
        self.description = description
        self.description_html = description_html
        self.categories = categories if categories else []
        self.tags = tags if tags else []
        self.group = group if group else Group()
        self.items = items
        self.url = url
        self.url_html = url_html
        self.metadata = metadata if metadata else Metadata()
        self.created_at = created_at

    def get_list(self):
        """Fetches a set of sets
        """
        target_url = self.get_url('SET', 'GET', 'multi')
        self._url = target_url
        return self

    def get(self, id):
        """Fetches a Set determined by the value of `id`.

        :param id: ID for the new :class:`Set` object.
        """

        target_url = self.get_url('SET', 'GET', 'single', {'set_id': id})

        dic_set_as_json = super(self.__class__, self).get(id, target_url)

        self._initialize_named_attributes(id = dic_set_as_json.get("id"),
                                          title = dic_set_as_json.get("title"),
                                          description = dic_set_as_json.get("description"),
                                          description_html = dic_set_as_json.get("description_html"),
                                          categories = make_list_of_Categories(dic_set_as_json.get("categories")),
                                          tags = dic_set_as_json.get("tags"),
                                          group = Group.from_dict(dic_set_as_json.get("group")),
                                          items = dic_set_as_json.get("items", []),
                                          url = dic_set_as_json.get("url"),
                                          url_html = dic_set_as_json.get("url_html"),
                                          metadata = Metadata.from_dict(dic_set_as_json.get("metadata")),
                                          created_at = make_date(dic_set_as_json.get("created_at")))



class Version(KoordinatesObjectMixin, KoordinatesURLMixin):
    '''A Version
    TODO: Explanation of what a `Version` is from Koordinates
    '''
    def __init__(self,
                 parent=None,
                 id=None,
                 url=None,
                 type=None,
                 name=None,
                 first_published_at=None,
                 published_at=None,
                 description=None,
                 description_html=None,
                 group=None,
                 data=None,
                 url_html=None,
                 published_version=None,
                 latest_version=None,
                 this_version=None,
                 kind=None,
                 categories=None,
                 tags=None,
                 collected_at=None,
                 created_at=None,
                 license=None,
                 metadata=None,
                 publish_to_catalog_services=None,
                 permissions=None,
                 autoupdate=None,
                 supplier_reference=None,
                 elevation_field=None,
                 version_instance=None):

        logger.info('Initializing Version object')
        self._parent = parent
        self._url = None

        self._raw_response = None
        self._list_of_response_dicts = []
        self._link_to_next_in_list = ""
        self._next_page_number = 1

        self._ordering_applied = False
        self._filtering_applied = False
        self._attribute_sort_candidates = ['name']
        self._attribute_filter_candidates = ['name']

        # An attribute may not be created automatically
        # due to JSON returned from the server with any
        # names which appear in the list
        # _attribute_reserved_names
        self._attribute_reserved_names = []


        self._initialize_named_attributes(id,
                                         url,
                                         type,
                                         name,
                                         first_published_at,
                                         published_at,
                                         description,
                                         description_html,
                                         group,
                                         data,
                                         url_html,
                                         published_version,
                                         latest_version,
                                         this_version,
                                         kind,
                                         categories,
                                         tags,
                                         collected_at,
                                         created_at,
                                         license,
                                         metadata,
                                         publish_to_catalog_services,
                                         permissions,
                                         autoupdate,
                                         supplier_reference,
                                         elevation_field,
                                         version_instance)

        super(self.__class__, self).__init__()

    def _initialize_named_attributes(self,
                                     id,
                                     url,
                                     type,
                                     name,
                                     first_published_at,
                                     published_at,
                                     description,
                                     description_html,
                                     group,
                                     data,
                                     url_html,
                                     published_version,
                                     latest_version,
                                     this_version,
                                     kind,
                                     categories,
                                     tags,
                                     collected_at,
                                     created_at,
                                     license,
                                     metadata,
                                     publish_to_catalog_services,
                                     permissions,
                                     autoupdate,
                                     supplier_reference,
                                     elevation_field,
                                     version_instance):
        '''
        `_initialize_named_attributes` initializes those
        attributes of `Version` which are not prefixed by an
        underbar. Such attributes are named so as to indicate
        that they are, in terms of the API, "real" attributes
        of a `Version`. That is to say an attribute which is returned
        from the server when a given `Version` is requested. Other
        attributes, such as `_attribute_reserved_names` have leading
        underbar to indicate they are not derived from data returned
        from the server

        '''

        self.id = id
        self.url = url
        self.type = type
        self.name = name
        self.first_published_at = first_published_at
        self.published_at = published_at
        self.description = description
        self.description_html = description_html
        self.group = group if group else Group()
        self.data = data if data else Data()
        self.url_html = url_html
        self.published_version = published_version
        self.latest_version = latest_version
        self.this_version = this_version
        self.kind = kind
        self.categories = categories if categories else []
        self.tags = tags if tags else []
        self.collected_at = collected_at
        self.created_at = created_at
        self.license = license if license else License()
        self.metadata = metadata if metadata else Metadata()
        self.publish_to_catalog_services = publish_to_catalog_services
        self.permissions = permissions
        self.autoupdate = autoupdate if autoupdate else Autoupdate()
        self.supplier_reference = supplier_reference
        self.elevation_field = elevation_field
        self.version_instance = version_instance if version_instance else Versioninstance()

    def get_list(self, layer_id):
        """Fetches a set of layers
        """
        target_url = self.get_url('VERSION', 'GET', 'multi', {'layer_id': layer_id})
        self._url = target_url
        return self

    def get(self, layer_id, version_id):
        """Fetches a version determined by the value of `version_id`.

        :param id: ID for the new :class:`Version` object.
        """

        target_url = self.get_url('VERSION', 'GET', 'single', {'layer_id': layer_id, 'version_id': version_id})
        dic_version_as_json = super(self.__class__, self).get(-1, target_url)

        self._initialize_named_attributes(id = dic_version_as_json.get("id"),
                                          url = dic_version_as_json.get("url"),
                                          type = dic_version_as_json.get("type"),
                                          name = dic_version_as_json.get("name"),
                                          first_published_at = make_date(dic_version_as_json.get("first_published_at")),
                                          published_at = make_date(dic_version_as_json.get("published_at")),
                                          description = dic_version_as_json.get("description"),
                                          description_html = dic_version_as_json.get("description_html"),
                                          group = Group.from_dict(dic_version_as_json.get("group")),
                                          data = Data.from_dict(dic_version_as_json.get("data")),
                                          url_html = dic_version_as_json.get("url_html"),
                                          published_version = dic_version_as_json.get("published_version"),
                                          latest_version = dic_version_as_json.get("latest_version"),
                                          this_version = dic_version_as_json.get("this_version"),
                                          kind = dic_version_as_json.get("kind"),
                                          categories = make_list_of_Categories(dic_version_as_json.get("categories")),
                                          tags = dic_version_as_json.get("tags"),
                                          collected_at = make_date_list_from_string_list(dic_version_as_json.get("collected_at", [])),
                                          created_at = make_date(dic_version_as_json.get("created_at")),
                                          license = License.from_dict(dic_version_as_json.get("license")),
                                          metadata = Metadata.from_dict(dic_version_as_json.get("metadata")),
                                          publish_to_catalog_services = dic_version_as_json.get("publish_to_catalog_services"),
                                          permissions = dic_version_as_json.get("permissions"),
                                          autoupdate = dic_version_as_json.get("autoupdate"),
                                          supplier_reference = dic_version_as_json.get("supplier_reference"),
                                          elevation_field = dic_version_as_json.get("elevation_field"),
                                          version_instance = Versioninstance.from_dict(dic_version_as_json.get("version")))

    def publish(self):
        """Publish the current Version
        """
        assert type(self.id) is int,\
            "The 'id' attribute is not an integer, it should be - have you fetched a version ?"
        assert type(self.version_instance.id) is int,\
            "The 'version_instance.id' attribute is not an integer, it should be - have you fetched a version ?"

        target_url = self.get_url('VERSION', 'POST', 'publish', {'layer_id': self.id, 'version_id': self.version_instance.id})
        json_headers = {'Content-type': 'application/json', 'Accept': '*/*'}
        self._raw_response = requests.post(target_url,
                                           headers=json_headers,
                                           auth=self._parent.get_auth())

        if self._raw_response.status_code == 201:
            # Success !
            pass
        elif self._raw_response.status_code == 404:
            # The resource specificed in the URL could not be found
            raise InvalidURL
        elif self._raw_response.status_code == 409:
            # Indicates that the request could not be processed because
            # of conflict in the request, such as an edit conflict in
            # the case of multiple updates
            raise ImportEncounteredUpdateConflict
        else:
            raise UnexpectedServerResponse

    def import_version(self, layer_id, version_id):
        """Reimport an existing layer from its previous datasources
        and create a new version
        """
        target_url = self.get_url('VERSION', 'POST', 'import', {'layer_id': layer_id, 'version_id': version_id})
        r = self._parent.request('POST', target_url)
        if r.status_code == 202:
            # Success ! Update accepted for Processing but not
            # necesarily complete
            pass
        elif r.status_code == 404:
            # The resource specificed in the URL could not be found
            raise InvalidURL
        elif r.status_code == 409:
            # Indicates that the request could not be processed because
            # of conflict in the request, such as an edit conflict in
            # the case of multiple updates
            raise ImportEncounteredUpdateConflict
        else:
            raise UnexpectedServerResponse


class Group(object):
    '''A Group
    TODO: Explanation of what a `Group` is from Koordinates

    NB: Currently this Class is only used as a component of `Layer`
    '''
    def __init__(self, id=None, url=None, name=None, country=None):
        self.id = id
        self.url = url
        self.name = name
        self.country = country

    @classmethod
    def from_dict(cls, dict_group):
        '''Initialize Group from a dict.

        la = Group.from_dict(a_dict)


        '''
        if dict_group:
            the_group = cls(dict_group.get("id", None),
                            dict_group.get("url", None),
                            dict_group.get("name", None),
                            dict_group.get("country", None))
        else:
            the_group = cls()

        return the_group


class Data(object):
    '''A Data
    TODO: Explanation of what a `Data` is from Koordinates

    NB: Currently `Data` is only used as a component of `Layer`
    '''
    def __init__(self, encoding=None, crs=None,
                 primary_key_fields=[],
                 datasources=[],
                 geometry_field=None,
                 fields=[]):

        assert type(primary_key_fields) is list,\
            "The 'Data' attribute 'primary_key_fields' must be a list"
        #assert type(datasources) is list,\
        #    "The 'Data' attribute 'datasources' must be a list"
        assert type(fields) is list,\
            "The 'Data' attribute 'fields' must be a list"
        #assert all(isinstance(ds_instance, Datasource) for ds_instance in datasources),\
        #    "The 'Data' attribute 'datasources' must be a list of Datasource objects"
        assert all(isinstance(f_instance, Field) for f_instance in fields),\
            "The 'Data' attribute 'fields' must be a list of Datasource objects"

        self.encoding = encoding
        self.crs = crs
        self.primary_key_fields = primary_key_fields
        self.datasources = datasources
        self.geometry_field = geometry_field
        self.fields = fields

    @classmethod
    def from_dict(cls, dict_data):
        '''Initialize Data from a dict.

        la = Data.from_dict(a_dict)


        '''
        if dict_data:
            # To allow for resuse across the API we allow for the
            # possibility that `datasources` is either : a string
            # (containing a url referencing a `datasources` object
            # or list of dictionaries defining one or more `datasources`
            # objects
            if isinstance(dict_data.get("datasources"), six.string_types):
                the_datasources = dict_data.get("datasources")
            else:
                the_datasources = make_list_of_Datasources(dict_data.get("datasources"))

            # Now build the `Data` object
            the_data = cls(dict_data.get("encoding"),
                           dict_data.get("crs"),
                           dict_data.get("primary_key_fields", []),
                           the_datasources,
                           dict_data.get("geometry_field"),
                           make_list_of_Fields(dict_data.get("fields")))
        else:
            the_data = cls()

        return the_data

class Datasource(object):
    '''A Datasource
    TODO: Explanation of what a `Datasource` is from Koordinates

    NB: Currently `Datasource` is only used as a component of `Layer`
    '''
    def __init__(self, id):
        self.id = id


class Category(object):
    '''A Category
    TODO: Explanation of what a `Category` is from Koordinates

    NB: Currently `Category` is only used as a component of `Layer`
    '''
    def __init__(self, name, slug):
        self.name = name
        self.slug = slug


class Autoupdate(object):
    '''A Autoupdate
    TODO: Explanation of what a `Autoupdate` is from Koordinates

    NB: Currently `Autoupdate` is only used as a component of `Version`
    '''
    def __init__(self, behaviour=None, schedule=None):
        self.behaviourk = behaviour
        self.schedule = schedule

    @classmethod
    def from_dict(cls, dict_autoupdate):
        '''Initialize License from a dict.

        la = License.from_dict(a_dict)


        '''
        if dict_autoupdate:
            the_autoupdate = cls(dict_autoupdate.get("behaviour"),
                                 dict_autoupdate.get("schedule"))
        else:
            the_autoupdate = cls()

        return the_autoupdate

class Createdby(object):
    '''A Createdby
    A basket of information identifying the creator
    '''
    def __init__(self,
                 id=None,
                 url=None,
                 first_name=None,
                 last_name=None,
                 country=None):

        self.id = id
        self.url = url
        self.first_name = first_name
        self.last_name = last_name
        self.country = country

    @classmethod
    def from_dict(cls, dict_createdby):
        '''Initialize Createdby from a dict.
        '''
        if dict_createdby:
            the_createdby = cls(dict_createdby.get("id"),
                              dict_createdby.get("url"),
                              dict_createdby.get("first_name"),
                              dict_createdby.get("last_name"),
                              dict_createdby.get("country"))
        else:
            the_createdby = cls()

        return the_createdby

class License(object):
    '''A License
    TODO: Explanation of what a `License` is from Koordinates

    NB: Currently `License` is only used as a component of `Layer`
    '''
    def __init__(self,
                 id=None,
                 title=None,
                 type=None,
                 jurisdiction=None,
                 version=None,
                 url=None,
                 url_html=None):

        self.id = id
        self.title = title
        self.type = type
        self.jurisdiction = jurisdiction
        self.version = version
        self.url = url
        self.url_html = url_html

    @classmethod
    def from_dict(cls, dict_license):
        '''Initialize License from a dict.

        la = License.from_dict(a_dict)


        '''
        if dict_license:
            the_license = cls(dict_license.get("id"),
                              dict_license.get("title"),
                              dict_license.get("type"),
                              dict_license.get("jurisdiction"),
                              dict_license.get("version"),
                              dict_license.get("url"),
                              dict_license.get("url_html"))
        else:
            the_license = cls()

        return the_license

class Versioninstance(object):
    '''A Versioninstance
    TODO: Explanation of what a `Versioninstance` is from Koordinates

    TODO: Rename this class `Versioninstance` is a very bad name for a
    class but I really wanted to push on when I encountered the need for the
    class.

    NB: Currently `Versioninstance` is only used as a component of `Version`
    '''
    def __init__(self,
                 id=None,
                 url=None,
                 status=None,
                 created_at=None,
                 created_by=None,
                 reference=None,
                 progress=None):

        self.id=id
        self.url=url
        self.status=status
        self.created_at=make_date(created_at)
        self.created_by=created_by
        self.reference=reference
        self.progress=progress

    @classmethod
    def from_dict(cls, dict_version_instance):
        '''Initialize License from a dict.

        la = License.from_dict(a_dict)


        '''
        if dict_version_instance:
            the_version_instance = cls(dict_version_instance.get("id"),
                              dict_version_instance.get("title"),
                              dict_version_instance.get("type"),
                              dict_version_instance.get("jurisdiction"),
                              dict_version_instance.get("version"),
                              dict_version_instance.get("url"),
                              dict_version_instance.get("url_html"))
        else:
            the_version_instance = cls()

        return the_version_instance

class Metadata(object):
    '''A Metadata
    TODO: Explanation of what a `Metadata` is from Koordinates

    NB: Currently `Metadata` is only used as a component of `Layer`
    '''
    def __init__(self, iso=None, dc=None, native=None):
        self.iso = iso
        self.dc = dc
        self.native = native

    @classmethod
    def from_dict(cls, dict_mdata):
        '''Initialize Metadata from a dict.

        la = Metadata.from_dict(a_dict)


        '''
        if dict_mdata:
            the_metadata = cls(dict_mdata.get("iso"),
                            dict_mdata.get("dc"),
                            dict_mdata.get("native"))
        else:
            the_metadata = cls()

        return the_metadata

class Field(object):
    '''A Field
    TODO: Explanation of what a `Field` is from Koordinates

    NB: Currently `Field` is only used as a component of `Layer`
    '''
    def __init__(self, name=None, type=None):
        self.name = name
        self.type = type


class Layer(KoordinatesObjectMixin, KoordinatesURLMixin):
    '''A Layer

    Layers are objects on the map that consist of one or more separate items,
    but are manipulated as a single unit. Layers generally reflect collections
    of objects that you add on top of the map to designate a common
    association.
    '''
    def __init__(self,
                 parent=None,
                 id=None,
                 url=None,
                 type=None,
                 name=None,
                 first_published_at=None,
                 published_at=None,
                 description=None,
                 description_html=None,
                 group=None,
                 data=None,
                 url_html=None,
                 published_version=None,
                 latest_version=None,
                 this_version=None,
                 kind=None,
                 categories=None,
                 tags=None,
                 collected_at=None,
                 created_at=None,
                 license=None,
                 metadata=None,
                 elevation_field=None):

        self._parent = parent
        self._url = None
        self._id = id
        self._ordering_applied = False
        self._filtering_applied = False

        self._raw_response = None
        self._list_of_response_dicts = []
        self._link_to_next_in_list = ""
        self._next_page_number = 1

        self._attribute_sort_candidates = ['name']
        self._attribute_filter_candidates = ['name']

        # An attribute may not be created automatically
        # due to JSON returned from the server with any
        # names which appear in the list
        # _attribute_reserved_names
        self._attribute_reserved_names = ['version']

        self._initialize_named_attributes(id,
                                         url,
                                         type,
                                         name,
                                         first_published_at,
                                         published_at,
                                         description,
                                         description_html,
                                         group,
                                         data,
                                         url_html,
                                         published_version,
                                         latest_version,
                                         this_version,
                                         kind,
                                         categories,
                                         tags,
                                         collected_at,
                                         created_at,
                                         license,
                                         metadata,
                                         elevation_field)

        super(self.__class__, self).__init__()

    def _initialize_named_attributes(self,
                                     id,
                                     url,
                                     type,
                                     name,
                                     first_published_at,
                                     published_at,
                                     description,
                                     description_html,
                                     group,
                                     data,
                                     url_html,
                                     published_version,
                                     latest_version,
                                     this_version,
                                     kind,
                                     categories,
                                     tags,
                                     collected_at,
                                     created_at,
                                     license,
                                     metadata,
                                     elevation_field):
        '''
        `_initialize_named_attributes` initializes those
        attributes of `Layer` which are not prefixed by an
        underbar. Such attributes are named so as to indicate
        that they are, in terms of the API, "real" attributes
        of a `Layer`. That is to say an attribute which is returned
        from the server when a given `Layer` is requested. Other
        attributes, such as `_attribute_reserved_names` have leading
        underbar to indicate they are not derived from data returned
        from the server

        '''

        self.id = id
        self.url = url
        self.type = type
        self.name = name
        self.first_published_at = first_published_at
        self.published_at = published_at
        self.description = description
        self.description_html = description_html
        self.group = group if group else Group()
        self.data = data if data else Data()
        self.url_html = url_html
        self.published_version = published_version
        self.latest_version = latest_version
        self.this_version = this_version
        self.kind = kind
        self.categories = categories if categories else []
        self.tags = tags if tags else []
        self.collected_at = collected_at
        self.created_at = created_at
        self.license = license if license else License()
        self.metadata = metadata if metadata else Metadata()
        self.elevation_field = elevation_field


    @classmethod
    def from_dict(cls, dict_layer):
        '''Initialize Layer from a dict.
        '''
        if dict_layer:
            the_layer = cls(None,
                            dict_layer.get("id", None),
                            dict_layer.get("url", None),
                            dict_layer.get("type", None),
                            dict_layer.get("name", None),
                            make_date(dict_layer.get("first_published_at", None)),
                            make_date(dict_layer.get("published_at", None)),
                            dict_layer.get("description", None),
                            dict_layer.get("description_html", None),
                            Group.from_dict(dict_layer.get("group", None)),
                            Data.from_dict(dict_layer.get("data", None)),
                            dict_layer.get("url_html", None),
                            dict_layer.get("published_version", None),
                            dict_layer.get("latest_version", None),
                            dict_layer.get("this_version", None),
                            dict_layer.get("kind", None),
                            make_list_of_Categories(dict_layer.get("categories", None)),
                            dict_layer.get("tags", None),
                            [make_date(str_date) for str_date in dict_layer.get("collected_at", [])],
                            make_date(dict_layer.get("created_at", None)),
                            License.from_dict(dict_layer.get("license", None)),
                            Metadata.from_dict(dict_layer.get("metadata", None)),
                            dict_layer.get("elevation_field", None))
        else:
            the_layer = cls()

        return the_layer


    def get_list(self):
        """Fetches a set of layers
        """
        target_url = self.get_url('LAYER', 'GET', 'multi')
        self._url = target_url
        return self

    def get_list_of_drafts(self):
        """Fetches a set of layers
        """
        target_url = self.get_url('LAYER', 'GET', 'multidraft')
        self._url = target_url
        return self

    def execute_get_list(self):
        """Fetches zero, one or more Layers .

        :param dynamic_build: When True the instance hierarchy arising from the
                              JSON returned is automatically build. When False
                              control is handed back to the calling subclass to
                              build the instance hierarchy based on pre-defined
                              classes.

                              An example of `dynamic_build` being False is that
                              the `Layer` class will have the JSON arising from
                              GET returned to it and will then follow processing
                              defined in `Layer.get` to create an instance of
                              `Layer` from the JSON returned.

                              NB: In later versions this flag will be withdrawn
                              and all processing will be done as if `dynamic_build`
                              was False.
        """
        for dic_layer_as_json in super(self.__class__, self).execute_get_list():
            the_layer =  Layer.from_dict(dic_layer_as_json)
            yield the_layer

    def get(self, id, dynamic_build = False):
        """Fetches a layer determined by the value of `id`.

        :param id: ID for the new :class:`Layer` object.
        """

        target_url = self.get_url('LAYER', 'GET', 'single', {'layer_id': id})
        # Call the superclass `get` with dynamic_build set to False
        dic_layer_as_json = super(self.__class__, self).get(id,
                                                            target_url,
                                                            dynamic_build)
        # Clear all existing attributes
        self._initialize_named_attributes(id = dic_layer_as_json.get("id"),
                                          url = dic_layer_as_json.get("url"),
                                          type = dic_layer_as_json.get("type"),
                                          name = dic_layer_as_json.get("name"),
                                          first_published_at = make_date(dic_layer_as_json.get("first_published_at")),
                                          published_at = make_date(dic_layer_as_json.get("published_at")),
                                          description = dic_layer_as_json.get("description"),
                                          description_html = dic_layer_as_json.get("description_html"),
                                          group = Group.from_dict(dic_layer_as_json.get("group")),
                                          data = Data.from_dict(dic_layer_as_json.get("data")),
                                          url_html = dic_layer_as_json.get("url_html"),
                                          published_version = dic_layer_as_json.get("published_version"),
                                          latest_version = dic_layer_as_json.get("latest_version"),
                                          this_version = dic_layer_as_json.get("this_version"),
                                          kind = dic_layer_as_json.get("kind"),
                                          categories = make_list_of_Categories(dic_layer_as_json.get("categories")),
                                          tags = dic_layer_as_json.get("tags"),
                                          collected_at = make_date_list_from_string_list(dic_layer_as_json.get("collected_at", [])),
                                          created_at = make_date(dic_layer_as_json.get("created_at")),
                                          license = License.from_dict(dic_layer_as_json.get("license")),
                                          metadata = Metadata.from_dict(dic_layer_as_json.get("metadata")),
                                          elevation_field = dic_layer_as_json.get("elevation_field"))


    def create(self):
        """Creates a layer based on the current attributes of the
        `Layer` instance.

        """
        target_url = self.get_url('LAYER', 'POST', 'create')
        super(self.__class__, self).create(target_url)

    def update(self):
        target_url = self.get_url('LAYER', 'POST', 'import')
        self._parent.request()
