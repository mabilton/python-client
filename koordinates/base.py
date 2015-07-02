import abc
import collections
import copy
import re

import six
from six.moves import urllib

from koordinates.exceptions import NotAValidBasisForOrdering


@six.add_metaclass(abc.ABCMeta)
class Manager(object):
    """
    Base class for Model Manager classes.

    Instantiated by the Model metaclass and attached to model._meta.manager.
    The Connection object needs to set itself on the Manager instance before it's used.
    """
    def __init__(self, model_class):
        self.model = model_class
        self.connection = None

    def _meta_attribute(self, attribute, default=None):
        return getattr(self.model._meta, attribute, default)

    def create_from_result(self, result):
        obj = self.model()
        obj.deserialize(result)
        return obj

    @abc.abstractmethod
    def get(self, target_url, id, expand=[]):
        headers = {}
        if expand:
            headers['Expand'] = ','.join(expand)

        r = self.connection.request('GET', target_url, headers=headers)
        r.raise_for_status()
        return self.create_from_result(r.json())

    @abc.abstractmethod
    def list(self, target_url):
        return Query(self.model, target_url)


class Query(object):
    """
    Chainable query class to manage GET requests for lists.
    Supports filtering by multiple attributes and sorting, and deals
    with pagination of resultsets into a single iterator.

    Query objects are instantiated by methods on the Manager classes.
    To actually execute the query, iterate over it. You can also call
    len() to return the length - this will do the "first" page request
    and examine the X-Resource-Range header to produce a count.
    """
    def __init__(self, model, url):
        self._model = model
        self._target_url = url
        self._count = None
        self._filters = collections.defaultdict(list)
        self._ordering = None
        self._expand = None

    @property
    def _manager(self):
        return self._model._meta.manager

    def _request(self, url):
        r = self._manager.connection.request('GET', url, headers=self._to_headers())
        r.raise_for_status()
        return r

    def _update_range(self, response):
        """ Update the query count property from the `X-Resource-Range` response header """
        header_value = response.headers.get('x-resource-range', '')
        m = re.match(r'\d+-\d+/(\d+)$', header_value)
        if m:
            self._count = int(m.group(1))
        else:
            self._count = None

    def _to_url(self):
        """ Serializes this query into a request-able URL including parameters """
        params = self._filters.copy()

        if self._ordering is not None:
            params['sort'] = self._ordering

        return self._target_url + "?" + urllib.parse.urlencode(params, doseq=True)

    def _to_headers(self):
        """ Serializes this query into a request-able set of headers """
        headers = {}
        if self._expand:
            headers['Expand'] = 'list'

        return headers

    def __iter__(self):
        """ Execute this query and return the results (generally as Model objects) """
        url = self._to_url()
        while url:
            r = self._request(url)
            page_results = r.json()

            # Update position
            self._update_range(r)

            for raw_result in page_results:
                yield self._manager.create_from_result(raw_result)

            # Paginate via Link headers
            # Link URLs will include the query parameters, so we can use it as an entire URL.
            url = r.links.get("next", None)

    def __len__(self):
        if self._count is None:
            r = self._request(self._to_url())
            self._update_range(r)
        return self._count

    def _clone(self):
        q = Query(self._model, self._target_url)
        q._filters = collections.defaultdict(list, copy.deepcopy(self._filters.items()))
        q._ordering = self._ordering
        q._expand = self._expand
        return q

    def filter(self, key, value):
        """
        Add a filter to this query.
        Appends to any previous filters set.
        """
        # Eventually this check will be a good deal more sophisticated
        # so it's here in its current form to some degree as a placeholder
        # if value.isspace():
        #     raise FilterMustNotBeSpaces()

        q = self._clone()
        q._filters[key].append(value)
        return q

    def order_by(self, sort_key=None):
        """
        Set the sort for this query. Not all attributes are sorting candidates.
        To sort in descending order, call `Query.order_by('-attribute')`.

        Calling `Query.order_by()` replaces any previous ordering.
        """
        if sort_key is not None:
            sort_attr = re.match(r'(-)?(.*)$', sort_key).group(2)
            if sort_attr not in self.manager._meta_attribute('attribute_sort_candidates', []):
                raise NotAValidBasisForOrdering(sort_key)

        q = self._clone()
        q._ordering = sort_key
        return q

    def expand(self):
        """
        Expand list results in this query.
        This can have a performance penalty for
        """
        q = self._clone()
        q._expand = True
        return q


class ModelMeta(type):
    """
    Sets up the special model characteristics based on the `Meta:` object on the model
    """
    def __new__(meta, name, bases, attrs):
        klass = super(ModelMeta, meta).__new__(meta, name, bases, attrs)
        try:
            Model
        except NameError:
            # klass is Model, it doesn't have a `Meta:` object
            pass
        else:
            if not hasattr(klass, "Meta"):
                raise AttributeError("Missing Meta object for %s" % klass)

            # Move model.Meta to model._meta
            klass._meta = klass.Meta
            del klass.Meta

            # Instantiate the Manager class, passing the model instance into it
            klass._meta.manager = klass._meta.manager(klass)
        return klass


@six.add_metaclass(ModelMeta)
class Model(object):
    """
    Base class for models with managers.

    Model subclasses need a Meta class, which (in particular)
    links to their Manager class:

    class FooManager(Manager):
        ...

    class Foo(Model):
        class Meta:
            manager = FooManager
            attribute_sort_candidates = []
            attribute_filter_candidates = []
            attribute_reserved_names = []
        ...
    """

    @property
    def _manager(self):
        return self._meta.manager

    @property
    def _connection(self):
        return self._manager.connection

    def deserialize(self, data):
        raise NotImplementedError()
