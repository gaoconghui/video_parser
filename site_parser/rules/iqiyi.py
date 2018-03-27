import hashlib
import json
import logging
import time

from site_parser.common import r1, get_content
from site_parser.rules.base import Parser, ParseJob

logger = logging.getLogger("parser.iqiyi")


class IqiyiParser(Parser):
    def __init__(self):
        pass

    def parse_url(self, url):
        pass


class IqiyiJob(ParseJob):
    stream_types = [
        {'id': '4k', 'container': 'm3u8', 'video_profile': '4k'},
        {'id': 'BD', 'container': 'm3u8', 'video_profile': '1080p'},
        {'id': 'TD', 'container': 'm3u8', 'video_profile': '720p'},
        {'id': 'TD_H265', 'container': 'm3u8', 'video_profile': '720p H265'},
        {'id': 'HD', 'container': 'm3u8', 'video_profile': '540p'},
        {'id': 'HD_H265', 'container': 'm3u8', 'video_profile': '540p H265'},
        {'id': 'SD', 'container': 'm3u8', 'video_profile': '360p'},
        {'id': 'LD', 'container': 'm3u8', 'video_profile': '210p'},
    ]

    ids = ['4k', 'BD', 'TD', 'HD', 'SD', 'LD']
    vd_2_id = {10: '4k', 19: '4k', 5: 'BD', 18: 'BD', 21: 'HD_H265', 2: 'HD', 4: 'TD', 17: 'TD_H265', 96: 'LD', 1: 'SD',
               14: 'TD'}
    id_2_profile = {'4k': '4k', 'BD': '1080p', 'TD': '720p', 'HD': '540p', 'SD': '360p', 'LD': '210p',
                    'HD_H265': '540p H265', 'TD_H265': '720p H265'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def parse(self):
        assert self.url

        if self.url and not self.vid:
            html = get_content(self.url, cookies=self.cookies)
            tvid = r1(r'#curid=(.+)_', self.url) or \
                   r1(r'tvid=([^&]+)', self.url) or \
                   r1(r'data-player-tvid="([^"]+)"', html) or r1(r'tv(?:i|I)d=(.+?)\&', html) or r1(
                r'param\[\'tvid\'\]\s*=\s*"(.+?)"', html)
            videoid = r1(r'#curid=.+_(.*)$', self.url) or \
                      r1(r'vid=([^&]+)', self.url) or \
                      r1(r'data-player-videoid="([^"]+)"', html) or r1(r'vid=(.+?)\&', html) or r1(
                r'param\[\'vid\'\]\s*=\s*"(.+?)"', html)
            self.vid = (tvid, videoid)
        tvid, videoid = self.vid
        info = self.getVMS(tvid, videoid)
        assert info['code'] == 'A00000', "can't play this video"

        for stream in info['data']['vidl']:
            try:
                stream_id = self.vd_2_id[stream['vd']]
                if stream_id in self.stream_types:
                    continue
                stream_profile = self.id_2_profile[stream_id]
                self.streams[stream_id] = {'video_profile': stream_profile, 'container': 'm3u8', 'src': [stream['m3u']],
                                           'size': 0, 'm3u8_url': stream['m3u']}
            except Exception as e:
                logger.info("vd: {} is not handled".format(stream['vd']))
                logger.info("info is {}".format(stream))

    def getVMS(self, tvid, vid):
        t = int(time.time() * 1000)
        src = '76f90cbd92f94a2e925d83e8ccd22cb7'
        key = 'd5fb4bd9d50c4be6948c97edd7254b0e'
        sc = hashlib.new('md5', bytes(str(t) + key + vid, 'utf-8')).hexdigest()
        vmsreq = 'http://cache.m.iqiyi.com/tmts/{0}/{1}/?t={2}&sc={3}&src={4}'.format(tvid, vid, t, sc, src)
        return json.loads(get_content(vmsreq, cookies=self.cookies))


if __name__ == '__main__':
    job = IqiyiJob("http://www.iqiyi.com/v_19rrifwzx2.html#vfrm=19-9-0-1")
    job.parse()
    print(job.streams)
