"""
The Koordinates Metadata API provides an interface for adding, inspecting
and downloading XML metadata documents against a range of objects.
"""

from . import base
from . import exceptions


class MetadataManager(base.InnerManager):
    def set(self, parent_url, fp):
        """
        If the parent object already has XML metadata, it will be overwritten.

        Accepts XML metadata in any of the three supported formats.
        The format will be detected from the XML content.

        The Metadata object becomes invalid after setting

        :param file fp: A reference to an open file-like object which the content will be read from.
        """
        url = parent_url + self.client.get_url_path('METADATA', 'POST', 'set', {})
        r = self.client.request('POST', url, data=fp, headers={'Content-type': 'text/xml'})
        if r.status_code != 204:
            raise exceptions.ServerError("Expected 204 response, got %s: %s" % (r.status_code, url))


class Metadata(base.InnerModel):
    FORMAT_ISO = 'iso'
    FORMAT_FGDC = 'fgdc'
    FORMAT_DC = 'dc'
    FORMAT_NATIVE = 'native'

    class Meta:
        manager = MetadataManager

    def get_xml(self, fp, format=FORMAT_NATIVE):
        """
        Returns the XML metadata for this source, converted to the requested format.
        Converted metadata may not contain all the same information as the native format.

        :param file fp: A reference to an open file which the content should be written to.
        :param str format: desired format for the output. This should be one of the available
            formats from :py:meth:`get_formats`_, or :py:const:`FORMAT_NATIVE`_ for the native format.
        """
        r = self._client.request('GET', getattr(self, format))
        for chunk in r.iter_content(65536):
            fp.write(chunk)

    def get_formats(self):
        """ Return the available format names for this metadata """
        formats = []
        for key in (self.FORMAT_DC, self.FORMAT_FGDC, self.FORMAT_ISO):
            if hasattr(self, key):
                formats.append(key)
        return formats
