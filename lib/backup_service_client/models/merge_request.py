# coding: utf-8

"""
    Couchbase Backup Service API

    This is REST API allows users to remotely schedule and run backups, restores and merges as well as to explore various archives for all there Couchbase Clusters.  # noqa: E501

    OpenAPI spec version: 0.1.0
    
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""

import pprint
import re  # noqa: F401

import six


class MergeRequest(object):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    """
    """
    Attributes:
      swagger_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    swagger_types = {
        'start': 'str',
        'end': 'str',
        'data_range': 'str'
    }

    attribute_map = {
        'start': 'start',
        'end': 'end',
        'data_range': 'data_range'
    }

    def __init__(self, start=None, end=None, data_range=None):  # noqa: E501
        """MergeRequest - a model defined in Swagger"""  # noqa: E501
        self._start = None
        self._end = None
        self._data_range = None
        self.discriminator = None
        if start is not None:
            self.start = start
        if end is not None:
            self.end = end
        if data_range is not None:
            self.data_range = data_range

    @property
    def start(self):
        """Gets the start of this MergeRequest.  # noqa: E501

        The option to pass the merge --start  # noqa: E501

        :return: The start of this MergeRequest.  # noqa: E501
        :rtype: str
        """
        return self._start

    @start.setter
    def start(self, start):
        """Sets the start of this MergeRequest.

        The option to pass the merge --start  # noqa: E501

        :param start: The start of this MergeRequest.  # noqa: E501
        :type: str
        """

        self._start = start

    @property
    def end(self):
        """Gets the end of this MergeRequest.  # noqa: E501

        The option to pass the merge --end  # noqa: E501

        :return: The end of this MergeRequest.  # noqa: E501
        :rtype: str
        """
        return self._end

    @end.setter
    def end(self, end):
        """Sets the end of this MergeRequest.

        The option to pass the merge --end  # noqa: E501

        :param end: The end of this MergeRequest.  # noqa: E501
        :type: str
        """

        self._end = end

    @property
    def data_range(self):
        """Gets the data_range of this MergeRequest.  # noqa: E501

        The option to pass to --data-range  # noqa: E501

        :return: The data_range of this MergeRequest.  # noqa: E501
        :rtype: str
        """
        return self._data_range

    @data_range.setter
    def data_range(self, data_range):
        """Sets the data_range of this MergeRequest.

        The option to pass to --data-range  # noqa: E501

        :param data_range: The data_range of this MergeRequest.  # noqa: E501
        :type: str
        """

        self._data_range = data_range

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value
        if issubclass(MergeRequest, dict):
            for key, value in self.items():
                result[key] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, MergeRequest):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
