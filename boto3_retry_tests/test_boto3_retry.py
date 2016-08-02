from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from botocore.exceptions import ClientError
import mock

from boto3_retry import _call_boto_func, _check_status_code, \
    _check_client_error, _check_generic_exception, _is_retryable, \
    Boto3RetryableException, retry_boto_func, retry_boto


def _generate_error(status_code=500, error_code='Error', operation_name='blah1'):
    return ClientError({
        'ResponseMetadata': {'HTTPStatusCode': status_code},
        'Error': {'Code': error_code}
    }, operation_name)


class TestIsRetryable(unittest.TestCase):
    def test__when_status_code_retryable__returns_true(self):
        self.assertTrue(_is_retryable(500, None, None, status_codes=[500]))

    def test__when_error_code_retryable__returns_true(self):
        self.assertTrue(_is_retryable(None, 'Error', None, error_codes=['Error']))

    def test__when_exception_retryable__returns_true(self):
        self.assertTrue(_is_retryable(None, None, ValueError('bllah'), exceptions=[ValueError]))

    def test__when_nothing_matches__returns_false(self):
        self.assertFalse(_is_retryable(None, None, None))


class TestCheckStatusCodes(unittest.TestCase):
    def test__when_invalid_status_code(self):
        resp = {'ResponseMetadata': {'HTTPStatusCode': 500}}
        self.assertRaises(Boto3RetryableException, _check_status_code, resp, 'blah', status_codes=[500])

    def test__when_valid_status_code__return(self):
        resp = {'ResponseMetadata': {'HTTPStatusCode': 200}}
        self.assertIsNone(_check_status_code(resp, 'blah', [500]))


class TestCheckClientError(unittest.TestCase):
    def test__when_retryable_error_code__throws_Boto3Retryable(self):
        exc = _generate_error(error_code='Error')
        self.assertRaises(Boto3RetryableException, _check_client_error, exc, 'blah', error_codes=['Error'])

    def test__when_retryable_status__throws_Boto3Retryable(self):
        exc =_generate_error(status_code=500)
        self.assertRaises(Boto3RetryableException, _check_client_error, exc, 'blah', status_codes=[500])

    def test__when_retry_all_client_error__throws_Boto3Retryable(self):
        exc = _generate_error()
        self.assertRaises(Boto3RetryableException, _check_client_error, exc, 'blah', exceptions=[ClientError])

    def test__when_not_retryable__throws_original_exception(self):
        exc = _generate_error()
        self.assertRaises(ClientError, _check_client_error, exc, 'blah')


class TestCheckGenericException(unittest.TestCase):
    def test__when_exception_retryable__raises_Boto3Retryable(self):
        exc = ValueError('blah')
        self.assertRaises(Boto3RetryableException, _check_generic_exception, exc, 'blah', exceptions=[ValueError])

    def test__when_exception_not_expected__raises_original(self):
        exc = AssertionError('blah')
        self.assertRaises(AssertionError, _check_generic_exception, exc, 'blah', exceptions=[ValueError])


class TestCallBotoFunc(unittest.TestCase):
    def test__when_catchable_error_code__raises_Retryable(self):
        def boto():
            raise _generate_error(error_code='Error')

        self.assertRaises(Boto3RetryableException, _call_boto_func, boto, retryable_codes=['Error'])

    def test__when_catchable_status_code__raises_Retryable(self):
        def boto():
            raise _generate_error(status_code=505)

        self.assertRaises(Boto3RetryableException, _call_boto_func, boto, retryable_status_codes=[505])

    def test__when_catchable_exception__raises_Retryable(self):
        def boto():
            raise ValueError('blah')

        self.assertRaises(Boto3RetryableException, _call_boto_func, boto, retryable_exceptions=[ValueError])

    def test__when_valid__returns_resp(self):
        def boto():
            return {'ResponseMetadata': {'HTTPStatusCode': 200}}

        resp = _call_boto_func(boto)
        self.assertDictEqual(boto(), resp)

    def test__when_uncatchable__throws_original(self):
        def boto():
            raise ArithmeticError()

        self.assertRaises(ArithmeticError, _call_boto_func, boto)


class TestRetryBotoFunc(unittest.TestCase):
    def test__when_retry_able_exception__retries(self):
        boto = mock.Mock(side_effect=_generate_error(error_code='Error'))
        self.assertRaises(Boto3RetryableException, retry_boto_func,
                          boto, max_retries=5, retry_wait_time=1, retryable_error_codes=['Error'])
        self.assertEqual(5, boto.call_count)

    def test__when_not_retryable__does_not_retry(self):
        boto = mock.Mock(side_effect=_generate_error(error_code='Error'))
        self.assertRaises(ClientError, retry_boto_func,
                          boto, max_retries=5, retry_wait_time=1)
        self.assertEqual(1, boto.call_count)


class TestRetryBotoDecorator(unittest.TestCase):
    def test__when_retryable_exception__retries(self):
        call = mock.Mock(side_effect=_generate_error(error_code='Error'))
        @retry_boto(max_retries=5, retry_wait_time=1, retryable_error_codes=['Error'])
        def boto():
            call()

        self.assertRaises(Boto3RetryableException, boto)
        self.assertEqual(5, call.call_count)

    def test__when_not_retryable__does_not_retry(self):

        call = mock.Mock(side_effect=_generate_error(error_code='Unexpected'))
        @retry_boto(max_retries=5, retry_wait_time=1, retryable_error_codes=['Error'])
        def boto():
            call()

        self.assertRaises(ClientError, boto)
        self.assertEqual(1, call.call_count)
