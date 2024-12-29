import math
from typing import List
import uuid
import time
import logging
import requests
from json.decoder import JSONDecodeError
from datetime import datetime
from functools import wraps
from re import fullmatch
from http import HTTPStatus

from flask import request, session
from pytz import utc

from config import TZ, MAINTENANCE_MODE, MAINTENANCE_MODE_MESSAGE
from src.types import GradeEntry


def check_missing_fields(data, *args):
    """
    Given a dict and a variable number of keys, returns a list of the keys that are not in the dict or
    that have empty values.
    :param data: a dict or dict-like object.
    :param args: any number of keys, typically strings.
    :return: a list of keys, or [] if all keys existed and had values.
    """
    missing = []
    for field in args:
        if field not in data:
            missing.append(field)
        elif isinstance(data[field], str) and len(data[field]) == 0:
            missing.append(field)
    return missing


def require_form(fields):
    """
    A decorator for POST routes that take form-encoded bodies; checks that all fields in the given list of field names
    exist and have non-empty values. If any fields are missing or empty, responds with a descriptive error message. If
    all fields have values, proceeds to the route handler function.
    :param fields: a list of field name strings.
    """

    def decorator_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            missing = check_missing_fields(request.form, *fields)
            missing_str = ", ".join(missing)
            if missing:
                return error("Missing or empty fields: %s." % missing_str)
            return func(*args, **kwargs)

        return wrapper

    return decorator_wrapper


def disable_in_maintenance_mode(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if MAINTENANCE_MODE:
            return "Broadway on Demand is currently under maintenance.\n{}".format(
                MAINTENANCE_MODE_MESSAGE
            ), 503
        return func(*args, **kwargs)

    return wrapper


def error(content, status=HTTPStatus.BAD_REQUEST):
    """
    Builds a response pair with the error content and status code. The Bad Request status is used if none is
    provided.
    :param content: The content of response, could be a string description.
    :param status: An HTTP status code for the response; Bad Request if not specified.
    """
    return content, status


def success(content, status=HTTPStatus.NO_CONTENT):
    """
    Builds a response pair with given response content and status code. The No Content (doesn't have to go away from
    current page) status is used if none is provided.
    :param content: The content of response, could be json data or string description
    :param status: An HTTP status code for the response; No Content if not specified
    """
    return content, status


def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = str(uuid.uuid4())
    return session["_csrf_token"]


def restore_csrf_token(value):
    session["_csrf_token"] = value


def verify_csrf_token(client_token):
    token = session.pop("_csrf_token", None)
    return token and token == client_token


def valid_id(id_str):
    return bool(fullmatch(r"[a-zA-Z0-9_.\-]+", id_str))


def parse_form_datetime(datetime_local_str):
    try:
        return TZ.localize(datetime.strptime(datetime_local_str, "%Y-%m-%dT%H:%M"))
    except ValueError:
        return None


def timestamp_to_iso(timestamp):
    return datetime.utcfromtimestamp(timestamp).isoformat()


def timestamp_round_up_minute(timestamp):
    if timestamp % 60 == 0:
        return timestamp
    return ((int(timestamp) // 60) * 60) + 60


def timestamp_to_bw_api_format(timestamp):
    return (
        datetime.utcfromtimestamp(timestamp)
        .replace(tzinfo=utc)
        .astimezone(TZ)
        .strftime("%Y-%m-%d %H:%M")
    )


def now_timestamp():
    return datetime.utcnow().replace(tzinfo=utc).timestamp()


def is_valid_netid(netid):
    """
    Return true if the NetID passed in is a valid NetId
    :param netid: A netid string to be tested
    """
    return fullmatch(r"[a-zA-Z0-9\-]+", netid) is not None


def is_valid_uin(uin):
    """
    Return true if the UIN passed in is a valid UIN (a 9-digit string).
    :param uin: A uin string to be tested
    """
    return fullmatch(r"\d{9}", uin) is not None


def is_valid_student(netid, uin, name):
    if not netid or not uin or not name:
        return False
    if not is_valid_netid(netid) or not is_valid_uin(uin):
        return False

    return True


def catch_request_errors(func):
    """
    Decorator used to catch common request errors such as RequestException,
    json decode error, etc.
    :return: None if the function raised exception
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (requests.exceptions.RequestException, KeyError, JSONDecodeError) as e:
            logging.error(
                "%s(args=%s, kwargs=%s): %s",
                func.__name__,
                str(args),
                str(kwargs),
                repr(e),
            )
            return None

    return wrapper


def test_slow_respond(func):
    """
    Decorator used to simulate slow server respond. Sleep a few seconds before processing
    the respond.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        time.sleep(3)
        return func(*args, **kwargs)

    return wrapper


def compute_statistics(name: str, entry_type: str, scores: List[float]) -> GradeEntry:
    """
    Compute statistics for an array of scores.
    """
    ROUNDING_DIGITS = 3
    if not scores:
        return GradeEntry(
            name=name,
            type=entry_type,
            score=0,
            min=0,
            q1=0,
            median=0,
            q3=0,
            max=0,
            mean=0,
            std=0
        )

    
    n = len(scores)
    
    # First pass: compute sum for mean and find min/max
    total = 0
    min_val = max_val = scores[0]
    
    for score in scores:
        total += score
        min_val = min(min_val, score)
        max_val = max(max_val, score)
    
    mean = total / n
    
    # Quick select implementation for O(n) median and quartiles
    def quick_select(arr: List[float], k: int, left: int, right: int) -> float:
        """
        Quick select algorithm to find the kth smallest element in O(n) time
        """
        while True:
            if left == right:
                return arr[left]
            
            # Choose pivot (using middle element to avoid worst case for sorted arrays)
            pivot_idx = (left + right) // 2
            pivot = arr[pivot_idx]
            
            # Move pivot to the end
            arr[pivot_idx], arr[right] = arr[right], arr[pivot_idx]
            
            # Partition
            store_idx = left
            for i in range(left, right):
                if arr[i] < pivot:
                    arr[store_idx], arr[i] = arr[i], arr[store_idx]
                    store_idx += 1
            
            # Move pivot to its final place
            arr[right], arr[store_idx] = arr[store_idx], arr[right]
            
            if store_idx == k:
                return arr[k]
            elif store_idx < k:
                left = store_idx + 1
            else:
                right = store_idx - 1
    
    # Create a copy of scores to avoid modifying the original array
    sorted_scores = scores.copy()
    
    # Find quartiles using quick select
    median_idx = (n - 1) // 2
    q1_idx = median_idx // 2
    q3_idx = median_idx + (n - median_idx) // 2
    
    median = quick_select(sorted_scores, median_idx, 0, n - 1)
    q1 = quick_select(sorted_scores, q1_idx, 0, median_idx)
    q3 = quick_select(sorted_scores, q3_idx, median_idx, n - 1)
    
    # Second pass: compute standard deviation
    squared_diff_sum = 0
    for score in scores:
        squared_diff_sum += (score - mean) ** 2
    std = math.sqrt(squared_diff_sum / n)
    
    return GradeEntry(
        name=name,
        type=entry_type,
        score=0,
        min=round(min_val, ROUNDING_DIGITS),
        q1=round(q1, ROUNDING_DIGITS),
        median=round(median, ROUNDING_DIGITS),
        q3=round(q3, ROUNDING_DIGITS),
        max=round(max_val, ROUNDING_DIGITS),
        mean=round(mean, ROUNDING_DIGITS),
        std=round(std, ROUNDING_DIGITS)
    )

def bin_scores(scores):
   bins = [0] * 10
   for score in scores:
       bin_idx = min(int(score // 10), 9)  
       bins[bin_idx] += 1
   return [[f"{i*10}-{min(100, (i+1)*10)}", count] for i, count in enumerate(bins)]