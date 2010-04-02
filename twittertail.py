#!/usr/bin/python
################################################################################
# twittertail.py
################################################################################
# Copyright 2010 Etienne Membrives <etienne@membrives.fr>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston MA 02110-1301, USA.
################################################################################

import twitter
import threading, time, Queue, locale, getopt
from optparse import OptionParser

class SearchProducer(threading.Thread):
    """Manages the Twitter search by regularily querying the API and adding new results to a shared queue."""
    def __init__(self,query,queue,delay,sync,lock):
        """query: string representing the query
        queue: Queue.Queue holding not-yet-displayed messages
        delay: int representing the delay between two queries
        sync: a consumer, used sync the next update of the queue
        lock: lock mechanism
        """
        self.__query=query
        self.__api=twitter.Api()
        self.__since=None
        self.__queue=queue
        self.__delay=delay
        self.__sync=sync
        self.__lock=lock
        self.__cont=True
        threading.Thread.__init__(self)

    def stop(self):
        """Stop the query"""
        self.__cont=False

    @property
    def delay(self):
        """Returns the delay between queries"""
        return self.__delay
    @property
    def query(self):
        """Returns the current query"""
        return self.__query

    def fetch_query(self):
        """Updates the queue by querying Twitter"""
        res=list(self.__api.Search(self.query,rpp=100,since_id=self.__since).results)
        self.__since=res[0].id
        res.reverse()
        for s in res:
            self.__queue.put(s)

    def run(self):
        """Run indefinitely"""
        while self.__cont:
            self.__lock.acquire()
            self.fetch_query()
            self.__lock.notify()
            self.__lock.release()
            self.__sync.set_nextrefresh(time.time()+self.__delay)
            time.sleep(self.__delay-1)

class DisplayConsumer(threading.Thread):
    """Manages the display of Twitter messages"""
    def __init__(self,queue,lock):
        """queue: Queue.Queue holding not-yet-displayed messages
        lock: lock mechanism
        """
        self.__queue=queue
        self.__nextrefresh=time.time()
        self.__cont=True
        self.__lock=lock
        threading.Thread.__init__(self)

    def set_nextrefresh(self,t):
        """Sets the next refresht time of the queue"""
        self.__nextrefresh=t

    def stop(self):
        """Stop displaying any new message and quit"""
        self.__cont=False

    def run(self):
        s="%a, %d %b %Y %H:%M:%S +0000"
        while self.__cont:
            self.__lock.acquire()
            if self.__queue.empty():
                self.__lock.wait()
            elem=self.__queue.get()
            self.__lock.release()
            #t=time.strptime(elem.created_at,s)
            #print elem.from_user+" ("+time.strftime("%c",t)+")"
            print elem.from_user+" ("+elem.created_at+", "+str(self.__queue.qsize())+")"
            print "> "+elem.text.replace('\n',' ').replace('  ',' ').replace('  ',' ')
            self.__queue.task_done()
            if self.__queue.qsize()!=0 and self.__nextrefresh > time.time():
                time.sleep((self.__nextrefresh-time.time())/float(self.__queue.qsize()))

# Here we define the program usage (as return by the flag --help)
# and we parse the command-line to populate internal variables
usage="usage: %prog [options] query"
option_parser=OptionParser(usage,version="%prog 0.1")
option_parser.add_option("-d", "--delay", dest="delay",
                  help="Delay (in seconds) between each Twitter query",default=60,type=int)
(options, args) = option_parser.parse_args()
query=args[0]
delay=options.delay

# Set up structures and threads
queue=Queue.Queue()
lock=threading.Lock()
cond=threading.Condition(lock)
dc=DisplayConsumer(queue,cond)
qp=SearchProducer(query,queue,delay,dc,cond)

# We want to use the system locale
locale.setlocale(locale.LC_ALL, '')

# .setDaemon(True) makes that the whole program ends as soon as the
# main thread ends
dc.setDaemon(True)
qp.setDaemon(True)

# Start everything
qp.start()
dc.start()

# While both threads are alive, continue
try:
    while qp.isAlive() and dc.isAlive():
        time.sleep(1)
# Catch the keyboard interrupt (^C), then quit
except KeyboardInterrupt:
    pass

print "Quitting ..."
qp.stop()
dc.stop()
