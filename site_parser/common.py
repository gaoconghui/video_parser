import re

from requests.sessions import Session


def get_content(url, method="GET", headers=None, cookies=None):
    with Session() as session:
        return session.request(method=method, url=url, headers=headers, cookies=cookies).text


def r1(pattern, text):
    m = re.search(pattern, text)
    if m:
        return m.group(1)
