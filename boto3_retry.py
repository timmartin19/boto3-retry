from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging

from botocore.exceptions import ClientError
from retrying import retry
import functools

__author__ = 'Tim Martin'
__email__ = 'tim@timmartin.me'
__version__ = '0.1.2'

LOG = logging.getLogger(__name__)


class Boto3RetryableException(Exception):
    """
    Thrown when encountering an exception
    from boto3 that can be retried safely
    """


def _call_boto_func(func, *args,
                    retryable_codes=None,
                    retryable_status_codes=None,
                    retryable_exceptions=None,
                    **kwargs):
    func_name = getattr(func, '__name__', 'unknown')
    LOG.debug('Calling %s', func_name)
    try:
        resp = func(*args, **kwargs)
    except ClientError as e:
        _check_client_error(e, func_name,
                            error_codes=retryable_codes,
                            status_codes=retryable_status_codes,
                            exceptions=retryable_exceptions)
    except Exception as e:
        _check_generic_exception(e, func_name, exceptions=retryable_exceptions)
    else:
        _check_status_code(resp, func_name, status_codes=retryable_status_codes)

    return resp


def _check_status_code(resp, func_name, status_codes=None):
    status_code = resp['ResponseMetadata']['HTTPStatusCode']
    if _is_retryable(status_code, None, None, status_codes=status_codes):
        raise Boto3RetryableException('Retrying %s due to %s status code', func_name, status_code)


def _check_client_error(exc, func_name, **kwargs):
    error_code = exc.response['Error']['Code']
    status_code = exc.response['ResponseMetadata']['HTTPStatusCode']
    LOG.warning('Failed to execute %s with status code %s '
                'due to error code %s', func_name, status_code, error_code)

    if _is_retryable(status_code, error_code, exc, **kwargs):
        LOG.warning('Encounter retryable status or error code: Error Code: %s, '
                    'Status Code: %s', error_code, status_code)
        raise Boto3RetryableException('Failed %s in retryable exception', func_name) from exc
    else:
        raise exc


def _check_generic_exception(exc, func_name, exceptions=None):
    if _is_retryable(None, None, exc, exceptions=exceptions):
        LOG.warning('Encountered retryable exception %s', type(exc))
        raise Boto3RetryableException('Failed %s in retryable exception', func_name) from exc
    else:
        raise exc


def _is_retryable(status_code, error_code, exc,
                  error_codes=None, status_codes=None, exceptions=None):
    error_codes = error_codes or []
    status_codes = status_codes or []
    exceptions = exceptions or []

    return status_code in status_codes or \
        error_code in error_codes or \
        type(exc) in exceptions


def retry_boto_func(func, *args,
                    retryable_error_codes=None,
                    retryable_status_codes=None,
                    retryable_exceptions=None,
                    max_retries=5,
                    retry_wait_time=2000,
                    **kwargs):
    retriable = retry(
        stop_max_attempt_number=max_retries,
        wait_exponential_multiplier=retry_wait_time,
        retry_on_exception=lambda exc: isinstance(exc, Boto3RetryableException)
    )(_call_boto_func)
    return retriable(func, *args,
                     retryable_status_codes=retryable_status_codes,
                     retryable_exceptions=retryable_exceptions,
                     retryable_codes=retryable_error_codes,
                     **kwargs)


def retry_boto(max_retries=5, retry_wait_time=2000, retryable_error_codes=None, retryable_status_codes=None, retryable_exceptions=None):
    def decorator(func):
        @functools.wraps(func)
        @retry(stop_max_attempt_number=max_retries,
               wait_exponential_multiplier=retry_wait_time,
               retry_on_exception=lambda exc: isinstance(exc, Boto3RetryableException))
        def wrapper(*args, **kwargs):
            return _call_boto_func(func, *args,
                                   retryable_status_codes=retryable_status_codes,
                                   retryable_exceptions=retryable_exceptions,
                                   retryable_codes=retryable_error_codes,
                                   **kwargs)
        return wrapper
    return decorator
