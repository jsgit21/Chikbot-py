import os
import requests


def _base():
    return os.getenv('WOM_API_BASE', 'https://api.wiseoldman.net/v2')


def _headers():
    return {'user-agent': os.getenv('WOM_USER_AGENT', 'chikbot')}


def get(path, params=None, timeout=10):
    url = _base() + path
    r = requests.get(url, headers=_headers(), params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def post(path, json=None, timeout=10):
    url = _base() + path
    r = requests.post(url, headers=_headers(), json=json, timeout=timeout)
    r.raise_for_status()
    return r.json()
