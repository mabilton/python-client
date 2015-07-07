# -*- coding: utf-8 -*-

"""
koordinates.sets
================

For grouping layers, tables and documents together.

"""

import logging

from .users import Group
from .metadata import Metadata, MetadataManager
from . import base
from .utils import is_bound


logger = logging.getLogger(__name__)


class SetManager(base.Manager):
    URL_KEY = 'SET'

    def __init__(self, client):
        super(SetManager, self).__init__(client)
        # Inner model managers
        self._metadata = MetadataManager(self, client)

    def create(self, set):
        target_url = self.client.get_url('SET', 'POST', 'create')
        r = self.client.request('POST', target_url, json=set.serialize())
        return set.deserialize(r.json(), self)

    def set_metadata(self, set_id, fp):
        base_url = self.client.get_url('SET', 'GET', 'single', {'id': set_id})
        self._metadata.set(base_url, fp)


class Set(base.Model):
    ''' For grouping layers, tables and documents together. '''
    class Meta:
        manager = SetManager

    def deserialize(self, data, manager):
        super(Set, self).deserialize(data, manager)
        self.group = Group().deserialize(data['group'], manager.client.get_manager(Group)) if data.get("group") else None
        self.metadata = Metadata().deserialize(data["metadata"], manager._metadata, self) if data.get("metadata") else None
        return self

    @is_bound
    def save(self):
        target_url = self._client.get_url('SET', 'PUT', 'update', {'id': self.id})
        r = self._client.request('PUT', target_url, json=self.serialize())
        return self.deserialize(r.json(), self._manager)

    @is_bound
    def set_metadata(self, fp):
        base_url = self._client.get_url('SET', 'GET', 'single', {'id': self.id})
        self._manager._metadata.set(base_url, fp)

        # reload myself
        r = self._client.request('GET', base_url)
        return self.deserialize(r.json(), self._manager)
