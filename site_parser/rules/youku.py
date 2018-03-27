import json
import logging
import re
import time
import urllib.parse
import urllib.request

from site_parser.common import get_content, r1
from site_parser.rules.base import Parser, ParseJob

logger = logging.getLogger("parser.youku")


class YoukuParser(Parser):
    referer = 'http://v.youku.com'
    mobile_ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36'

    def __init__(self, cookies):
        self.cookies = cookies

    def parse_url(self, url):
        youku_parser_job = YoukuJob(url=url, referer=self.referer, ua=self.mobile_ua)
        youku_parser_job.parse()
        # TODO check if job done
        return youku_parser_job.streams


class YoukuJob(ParseJob):
    dispatcher_url = 'vali.cp31.ott.cibntv.net'

    stream_types = [
        {'id': 'hd3', 'container': 'flv', 'video_profile': '1080P'},
        {'id': 'hd3v2', 'container': 'flv', 'video_profile': '1080P'},
        {'id': 'mp4hd3', 'container': 'mp4', 'video_profile': '1080P'},
        {'id': 'mp4hd3v2', 'container': 'mp4', 'video_profile': '1080P'},

        {'id': 'hd2', 'container': 'flv', 'video_profile': '超清'},
        {'id': 'hd2v2', 'container': 'flv', 'video_profile': '超清'},
        {'id': 'mp4hd2', 'container': 'mp4', 'video_profile': '超清'},
        {'id': 'mp4hd2v2', 'container': 'mp4', 'video_profile': '超清'},

        {'id': 'mp4hd', 'container': 'mp4', 'video_profile': '高清'},
        # not really equivalent to mp4hd
        {'id': 'flvhd', 'container': 'flv', 'video_profile': '渣清'},
        {'id': '3gphd', 'container': 'mp4', 'video_profile': '渣清'},

        {'id': 'mp4sd', 'container': 'mp4', 'video_profile': '标清'},
        # obsolete?
        {'id': 'flv', 'container': 'flv', 'video_profile': '标清'},
        {'id': 'mp4', 'container': 'mp4', 'video_profile': '标清'},
    ]

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.page = None
        self.video_list = None
        self.video_next = None
        self.api_data = None
        self.api_error_code = None
        self.api_error_msg = None

        self.ccode = '0590'
        self.utid = None

    def youku_ups(self):
        url = 'https://ups.youku.com/ups/get.json?vid={}&ccode={}'.format(self.vid, self.ccode)
        url += '&client_ip=192.168.1.1'
        url += '&utid=' + self.utid
        url += '&client_ts=' + str(int(time.time()))
        headers = dict(Referer=self.referer)
        headers['User-Agent'] = self.ua
        api_meta = json.loads(get_content(url, headers=headers))

        self.api_data = api_meta['data']
        data_error = self.api_data.get('error')
        if data_error:
            self.api_error_code = data_error.get('code')
            self.api_error_msg = data_error.get('note')
        if 'videos' in self.api_data:
            if 'list' in self.api_data['videos']:
                self.video_list = self.api_data['videos']['list']
            if 'next' in self.api_data['videos']:
                self.video_next = self.api_data['videos']['next']

    @classmethod
    def change_cdn(cls, url):
        # if the cnd_url starts with an ip addr, it should be youku's old CDN
        # which rejects http requests randomly with status code > 400
        # change it to the dispatcher of aliCDN can do better
        # at least a little more recoverable from HTTP 403
        if cls.dispatcher_url in url:
            return url
        elif 'k.youku.com' in url:
            return url
        else:
            url_seg_list = list(urllib.parse.urlsplit(url))
            url_seg_list[1] = cls.dispatcher_url
            return urllib.parse.urlunsplit(url_seg_list)

    def fetch_cna(self):

        def quote_cna(val):
            if '%' in val:
                return val
            return urllib.parse.quote(val)

        if self.cookies:
            for cookie in self.cookies:
                if cookie.name == 'cna' and cookie.domain == '.youku.com':
                    logger.info('Found cna in imported cookies. Use it')
                    return quote_cna(cookie.value)
        url = 'http://log.mmstat.com/eg.js'
        req = urllib.request.urlopen(url)
        headers = req.getheaders()
        for header in headers:
            if header[0].lower() == 'set-cookie':
                n_v = header[1].split(';')[0]
                name, value = n_v.split('=')
                if name == 'cna':
                    return quote_cna(value)
        logger.warning('It seems that the client failed to fetch a cna cookie. Please load your own cookie if possible')
        return quote_cna('DOG4EdW4qzsCAbZyXbU+t7Jt')

    def get_vid_from_url(self):
        # It's unreliable. check #1633
        b64p = r'([a-zA-Z0-9=]+)'
        if not self.url:
            raise Exception('No url')
        self.vid = r1(self.url, r'youku\.com/v_show/id_' + b64p) or \
                   r1(self.url, r'player\.youku\.com/player\.php/sid/' + b64p + r'/v\.swf') or \
                   r1(self.url, r'loader\.swf\?VideoIDS=' + b64p) or \
                   r1(self.url, r'player\.youku\.com/embed/' + b64p)

    def get_vid_from_page(self):
        if not self.url:
            raise Exception('No url')
        self.page = get_content(self.url)
        hit = re.search(r'videoId2:"([A-Za-z0-9=]+)"', self.page)
        if hit is not None:
            self.vid = hit.group(1)

    def parse(self):
        assert self.url or self.vid

        if self.url and not self.vid:
            self.get_vid_from_url()

            if self.vid is None:
                self.get_vid_from_page()

                if self.vid is None:
                    logger.info('Cannot fetch vid')

        self.utid = self.fetch_cna()
        self.youku_ups()

        if self.api_data.get('stream') is None:
            if self.api_error_code == -6001:  # wrong vid parsed from the page
                vid_from_url = self.vid
                self.get_vid_from_page()
                if vid_from_url == self.vid:
                    logger.info(self.api_error_msg)
                self.youku_ups()

        if self.api_data.get('stream') is None:
            if self.api_error_msg:
                logger.info(self.api_error_msg)
            else:
                logger.info('Unknown error')

        self.title = self.api_data['video']['title']
        stream_types = dict([(i['id'], i) for i in self.stream_types])
        audio_lang = self.api_data['stream'][0]['audio_lang']

        for stream in self.api_data['stream']:
            stream_id = stream['stream_type']
            is_preview = False
            if stream_id in stream_types and stream['audio_lang'] == audio_lang:
                if 'alias-of' in stream_types[stream_id]:
                    stream_id = stream_types[stream_id]['alias-of']

                if stream_id not in self.streams:
                    self.streams[stream_id] = {
                        'container': stream_types[stream_id]['container'],
                        'video_profile': stream_types[stream_id]['video_profile'],
                        'size': stream['size'],
                        'pieces': [{
                            'segs': stream['segs']
                        }],
                        'm3u8_url': stream['m3u8_url']
                    }
                    src = []
                    for seg in stream['segs']:
                        if seg.get('cdn_url'):
                            src.append(self.__class__.change_cdn(seg['cdn_url']))
                        else:
                            is_preview = True
                    self.streams[stream_id]['src'] = src
                else:
                    self.streams[stream_id]['size'] += stream['size']
                    self.streams[stream_id]['pieces'].append({
                        'segs': stream['segs']
                    })
                    src = []
                    for seg in stream['segs']:
                        if seg.get('cdn_url'):
                            src.append(self.__class__.change_cdn(seg['cdn_url']))
                        else:
                            is_preview = True
                    self.streams[stream_id]['src'].extend(src)
                    # if is_preview:
                    #     logger.warning(('{} is a preview'.format(stream_id)))

        # Audio languages
        if 'dvd' in self.api_data:
            al = self.api_data['dvd'].get('audiolang')
            if al:
                self.audiolang = al
                for i in self.audiolang:
                    i['url'] = 'http://v.youku.com/v_show/id_{}'.format(i['vid'])


if __name__ == '__main__':
    job = YoukuJob("http://v.youku.com/v_show/id_XMzQyOTA3NjQ2OA==.html?from=s1.8-3-1.1")
    job.parse()
    print(job.streams)
