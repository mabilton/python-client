# -*- coding: utf-8 -*-

"""
koordinates.api
~~~~~~~~~~~~
This module implements the Koordinates API.

:copyright: (c) Koordinates .
:license: BSD, see LICENSE for more details.
"""

import logging
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

import six
import requests

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
from .mixins import (
    KoordinatesURLMixin,
    KoordinatesObjectMixin
)

from .layer import (
    Version,
    Group,
    Data,
    Datasource,
    Category,
    Autoupdate,
    Createdby,
    License,
    Versioninstance,
    Metadata,
    Field,
    Layer,
)
SUPPORTED_API_VERSIONS = ['v1', 'UNITTESTINGONLY']


logger = logging.getLogger(__name__)


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



