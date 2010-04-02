#!/usr/bin/python
######################################################################
# twittertail.py
######################################################################
# Copyright 2010 Etienne Membrives <etienne@membrives.fr>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 3 of the License.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston MA 02110-1301, USA.

import twitter
import threading, time, Queue, locale, getopt
from optparse import OptionParser

class SearchProducer(threading.Thread):
    def __init__(self,query,queue,refreshrate,sync,lock):
        self.__query=query
        self.__api=twitter.Api()
        self.__since=None
        self.__queue=queue
        self.__refreshrate=refreshrate
        self.__sync=sync
        self.__lock=lock
        self.__cont=True
        threading.Thread.__init__(self)

    def stop(self):
        self.__cont=False

    @property
    def refreshrate(self):
        return self.__refreshrate
    @property
    def query(self):
        return self.__query

    def fetch_query(self):
        res=list(self.__api.Search(self.query,rpp=100,since_id=self.__since).results)
        self.__since=res[0].id
        res.reverse()
        for s in res:
            self.__queue.put(s)

    def run(self):
        while self.__cont:
            self.__lock.acquire()
            self.fetch_query()
            self.__lock.notify()
            self.__lock.release()
            self.__sync.set_nextrefresh(time.time()+self.__refreshrate)
            time.sleep(self.__refreshrate-1)

class DisplayConsumer(threading.Thread):
    def __init__(self,queue,lock):
        self.__queue=queue
        self.__nextrefresh=time.time()
        self.__cont=True
        self.__lock=lock
        threading.Thread.__init__(self)

    def set_nextrefresh(self,t):
        self.__nextrefresh=t

    def stop(self):
        self.__cont=False

    def run(self):
        s="%a, %d %b %Y %H:%M:%S +0000"
        while self.__cont:
            elem=self.__queue.get()
            #t=time.strptime(elem.created_at,s)
            #print elem.from_user+" ("+time.strftime("%c",t)+")"
            print elem.from_user+" ("+elem.created_at+", "+str(self.__queue.qsize())+")"
            print "> "+elem.text.replace('\n',' ').replace('  ',' ').replace('  ',' ')
            self.__queue.task_done()
            if self.__queue.qsize()!=0 and self.__nextrefresh > time.time():
                time.sleep((self.__nextrefresh-time.time())/float(self.__queue.qsize()))


usage="usage: %prog [options] query"
option_parser=OptionParser(usage,version="%prog 0.1")
option_parser.add_option("-r", "--refresh-rate", dest="delay",
                  help="Delay (in seconds) between each Twitter query",default=60,type=int)
(options, args) = option_parser.parse_args()
query=args[0]
refreshrate=options.delay

queue=Queue.Queue()
lock=threading.Lock()
cond=threading.Condition(lock)
dc=DisplayConsumer(queue,cond)
qp=SearchProducer(query,queue,refreshrate,dc,cond)

locale.setlocale(locale.LC_ALL, '')

dc.setDaemon(True)
qp.setDaemon(True)
qp.start()
dc.start()

try:
    while qp.isAlive() and dc.isAlive():
        time.sleep(1)
except KeyboardInterrupt:
    pass

print "Quitting ..."
qp.stop()
dc.stop()
