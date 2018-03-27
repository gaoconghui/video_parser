# -*- coding: utf-8 -*-

class Parser(object):
    """
    parser是一个任务工厂，保存了一些全局的参数，比如一个视频网站的cookie池，账号池
    """

    def can_parse(self, url):
        """
        该url是否可以解析
        :return: 
        """
        return True

    def parse_url(self, url):
        """
        输入url必须是这个站点的url
        :return: 
        """
        raise NotImplementedError()


class ParseJob(object):
    """
    保存一个视频解析过程中产生的参数
    """

    def __init__(self, *args, **kwargs):
        self.url = None
        self.title = None
        self.vid = None
        self.streams = {}
        self.streams_sorted = []
        self.audiolang = None
        self.dash_streams = {}
        self.referer = kwargs.get("referer")
        self.ua = kwargs.get("ua")
        self.cookies = kwargs.get("cookies")
        self.danmuku = None

        if args:
            self.url = args[0]

    def parse(self):
        raise NotImplementedError()


class ParseResult(object):
    """
    封装解析的结果
    """
