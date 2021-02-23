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


class CloudCredentials(object):
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
        'name': 'str',
        'provider': 'str',
        'key': 'str',
        'id': 'str'
    }

    attribute_map = {
        'name': 'name',
        'provider': 'provider',
        'key': 'key',
        'id': 'id'
    }

    def __init__(self, name=None, provider=None, key=None, id=None):  # noqa: E501
        """CloudCredentials - a model defined in Swagger"""  # noqa: E501
        self._name = None
        self._provider = None
        self._key = None
        self._id = None
        self.discriminator = None
        if name is not None:
            self.name = name
        if provider is not None:
            self.provider = provider
        if key is not None:
            self.key = key
        if id is not None:
            self.id = id

    @property
    def name(self):
        """Gets the name of this CloudCredentials.  # noqa: E501

        The name used to identify the credentials  # noqa: E501

        :return: The name of this CloudCredentials.  # noqa: E501
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name):
        """Sets the name of this CloudCredentials.

        The name used to identify the credentials  # noqa: E501

        :param name: The name of this CloudCredentials.  # noqa: E501
        :type: str
        """

        self._name = name

    @property
    def provider(self):
        """Gets the provider of this CloudCredentials.  # noqa: E501

        The provider this credentials are for.  # noqa: E501

        :return: The provider of this CloudCredentials.  # noqa: E501
        :rtype: str
        """
        return self._provider

    @provider.setter
    def provider(self, provider):
        """Sets the provider of this CloudCredentials.

        The provider this credentials are for.  # noqa: E501

        :param provider: The provider of this CloudCredentials.  # noqa: E501
        :type: str
        """
        allowed_values = ["AWS"]  # noqa: E501
        if provider not in allowed_values:
            raise ValueError(
                "Invalid value for `provider` ({0}), must be one of {1}"  # noqa: E501
                .format(provider, allowed_values)
            )

        self._provider = provider

    @property
    def key(self):
        """Gets the key of this CloudCredentials.  # noqa: E501

        The secret key used to access the store. Note this value will not be displayed on get requests.  # noqa: E501

        :return: The key of this CloudCredentials.  # noqa: E501
        :rtype: str
        """
        return self._key

    @key.setter
    def key(self, key):
        """Sets the key of this CloudCredentials.

        The secret key used to access the store. Note this value will not be displayed on get requests.  # noqa: E501

        :param key: The key of this CloudCredentials.  # noqa: E501
        :type: str
        """

        self._key = key

    @property
    def id(self):
        """Gets the id of this CloudCredentials.  # noqa: E501

        The key id used to access the store. Note this value will not be returned either.  # noqa: E501

        :return: The id of this CloudCredentials.  # noqa: E501
        :rtype: str
        """
        return self._id

    @id.setter
    def id(self, id):
        """Sets the id of this CloudCredentials.

        The key id used to access the store. Note this value will not be returned either.  # noqa: E501

        :param id: The id of this CloudCredentials.  # noqa: E501
        :type: str
        """

        self._id = id

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
        if issubclass(CloudCredentials, dict):
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
        if not isinstance(other, CloudCredentials):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
