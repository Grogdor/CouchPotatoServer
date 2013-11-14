from bs4 import BeautifulSoup
from couchpotato.core.helpers.encoding import toUnicode, tryUrlencode
from couchpotato.core.helpers.variable import tryInt, cleanHost
from couchpotato.core.logger import CPLog
from couchpotato.core.providers.torrent.base import TorrentMagnetProvider
from couchpotato.environment import Env
import re
import time
import traceback

log = CPLog(__name__)


class KickAssTorrents(TorrentMagnetProvider):

    urls = {
        'detail': '%s/%s',
        'search': '%s/%s-i%s/',
    }

    cat_ids = [
        (['cam'], ['cam']),
        (['telesync'], ['ts', 'tc']),
        (['screener', 'tvrip'], ['screener']),
        (['x264', '720p', '1080p', 'blu-ray', 'hdrip'], ['bd50', '1080p', '720p', 'brrip']),
        (['dvdrip'], ['dvdrip']),
        (['dvd'], ['dvdr']),
    ]

    http_time_between_calls = 1 #seconds
    cat_backup_id = None

    proxy_list = [
        'https://kickass.to',
        'http://kickasstorrents.come.in',
        'http://kickass.pw',
        'http://www.kickassunblock.info',
        'http://www.kickassproxy.info',
    ]

    def __init__(self):
        self.domain = self.conf('domain')
        super(KickAssTorrents, self).__init__()

    def _search(self, movie, quality, results):

        data = self.getHTMLData(self.urls['search'] % (self.getDomain(), 'm', movie['library']['identifier'].replace('tt', '')))
        
        if data:

            cat_ids = self.getCatId(quality['identifier'])
            table_order = ['name', 'size', None, 'age', 'seeds', 'leechers']

            try:
                html = BeautifulSoup(data)
                resultdiv = html.find('div', attrs = {'class':'tabs'})
                for result in resultdiv.find_all('div', recursive = False):
                    if result.get('id').lower().strip('tab-') not in cat_ids:
                        continue

                    try:
                        for temp in result.find_all('tr'):
                            if temp['class'] is 'firstr' or not temp.get('id'):
                                continue

                            new = {}

                            nr = 0
                            for td in temp.find_all('td'):
                                column_name = table_order[nr]
                                if column_name:

                                    if column_name == 'name':
                                        link = td.find('div', {'class': 'torrentname'}).find_all('a')[1]
                                        new['id'] = temp.get('id')[-8:]
                                        new['name'] = link.text
                                        new['url'] = td.find('a', 'imagnet')['href']
                                        new['detail_url'] = self.urls['detail'] % (self.getDomain(), link['href'][1:])
                                        new['score'] = 20 if td.find('a', 'iverif') else 0
                                    elif column_name is 'size':
                                        new['size'] = self.parseSize(td.text)
                                    elif column_name is 'age':
                                        new['age'] = self.ageToDays(td.text)
                                    elif column_name is 'seeds':
                                        new['seeders'] = tryInt(td.text)
                                    elif column_name is 'leechers':
                                        new['leechers'] = tryInt(td.text)

                                nr += 1

                            results.append(new)
                    except:
                        log.error('Failed parsing KickAssTorrents: %s', traceback.format_exc())

            except AttributeError:
                log.debug('No search results found.')

    def ageToDays(self, age_str):
        age = 0
        age_str = age_str.replace('&nbsp;', ' ')

        regex = '(\d*.?\d+).(sec|hour|day|week|month|year)+'
        matches = re.findall(regex, age_str)
        for match in matches:
            nr, size = match
            mult = 1
            if size == 'week':
                mult = 7
            elif size == 'month':
                mult = 30.5
            elif size == 'year':
                mult = 365

            age += tryInt(nr) * mult

        return tryInt(age)


    def isEnabled(self):
        return super(KickAssTorrents, self).isEnabled() and self.getDomain()

    def getDomain(self, url = ''):

        if not self.domain:
            for proxy in self.proxy_list:

                prop_name = 'kat_proxy.%s' % proxy
                last_check = float(Env.prop(prop_name, default = 0))
                if last_check > time.time() - 1209600:
                    continue

                data = ''
                try:
                    data = self.urlopen(proxy, timeout = 3, show_error = False)
                except:
                    log.debug('Failed kat proxy %s', proxy)

                if 'placeholder="Search query"' in data:
                    log.debug('Using proxy: %s', proxy)
                    self.domain = proxy
                    break

                Env.prop(prop_name, time.time())

        if not self.domain:
            log.error('No kat proxies left, please add one in settings, or let us know which one to add on the forum.')
            return None

        return cleanHost(self.domain).rstrip('/') + url
