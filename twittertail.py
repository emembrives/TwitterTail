import twitter, threading, time, Queue, locale

class SearchProducer(threading.Thread):
    def __init__(self,query,queue,refreshrate,sync):
        self.__query=query
        self.__api=twitter.Api()
        self.__since=None
        self.__queue=queue
        self.__refreshrate=refreshrate
        self.__sync=sync
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
            self.fetch_query()
            self.__sync.set_nextrefresh(time.time()+self.__refreshrate)
            time.sleep(self.__refreshrate-1)

class DisplayConsumer(threading.Thread):
    def __init__(self,queue):
        self.__queue=queue
        self.__nextrefresh=time.time()
        self.__cont=True
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

query=raw_input("Twitter query: ")

queue=Queue.Queue()
dc=DisplayConsumer(queue)
qp=SearchProducer(query,queue,60,dc)

locale.setlocale(locale.LC_ALL, '')


qp.start()
qp.daemon=True
dc.start()
dc.daemon=True

s=''
while s!='q' and qp.isAlive() and dc.isAlive():
    s=raw_input()

qp.stop()
dc.stop()
qp.join()
dc.join()
