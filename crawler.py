import urllib
import urllib2
import re
import robotparser
import urlparse
import output_format
import datetime
from Queue import Queue
import threading
import time
import configuration
import sys


class MyThread(threading.Thread):
    func = None
    def __init__(self, func):
        super(MyThread, self).__init__()
        self.func = func
    def run(self):
        self.func()



class web_crawler:
    domain = ""
    crawled_webs = set([])
    has_robot = False
    robot_parse = None
    web_queue = Queue()
    thread_num = 8
    threads = []
    file_lock = None
    excluded_url = set([])
    excluded_img = set([])
    response_code = {}
    urlregex = re.compile('<a [^>]*href=[\'|"](.*?)[\'|"].*?>')
    user_agent = 'User-Agent:Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_4)'
    output = None

    def __init__(self,domain = "http://www.hanzhaodeng.com/",file = configuration.file_location):

        if(domain[len(domain)-1] == '/'):
            domain = domain[:len(domain)-1]

        if domain.startswith("http") or domain.startswith("https"):
            self.domain = domain
        else:
            self.domain = "http://" + domain

        self.web_queue.put(self.domain)

        # Clear the output file
        self.output = open(file,'w')

        #initiaize file lock
        self.file_lock = threading.Lock()


        # Check robot.txt
        robot_url = self.domain + '/' + 'robots.txt'
        request = urllib2.Request(robot_url,headers = {"User-Agent":self.user_agent})
        try:
            response = urllib2.urlopen(request)
        except Exception, e:
            print 'websit: ' + self.domain + ' has no robot.txt'
        else:
            self.has_robot = True
            self.robot_parser = robotparser.RobotFileParser()
            self.robot_parser.set_url(self.domain + "/robots.txt")
            self.robot_parser.read()


    def run(self):

        self.output.write(output_format.header)

        for i in xrange(self.thread_num):
            thread = MyThread(self.crawl_web)
            thread.start()
            time.sleep(1)
            # print "Thread " + str(i) + "start"
            self.threads.append(thread)

        for thread in self.threads:
            thread.join

        self.web_queue.join()

        # while(self.web_queue):
        #     self.crawl_web()
        print 'Done\n'
        self.output.write(output_format.footer)
        self.output.close

        print "Number of Crawled urls : " + str(len(self.crawled_webs))

    def crawl_web(self):
        while not self.web_queue.empty():
            towrite = ""
            current_url = self.web_queue.get()
            print current_url
            self.crawled_webs.add(current_url)
            request = urllib2.Request(current_url, headers={'User-Agent': self.user_agent})
            try:
                response = urllib2.urlopen(request)
            except Exception, e:
                if hasattr(e,'code'):
				    if e.code in self.response_code:
					    self.response_code[e.code]+=1
				    else:
					    self.response_code[e.code]=1
                self.web_queue.task_done()
            else:
                # self.output.write("<url>\n  <loc>" + current_url + "</loc>\n")
                code = response.getcode()
                if code in self.response_code:
                    self.response_code[code] += 1
                else:
                    self.response_code[code] = 1
                towrite = towrite + "<url><loc>" + current_url + "</loc>"
                web_content = response.read()
                towrite_link = self.get_links(web_content)
                towrite_img = self.get_imgs(web_content)
                if(towrite_link):
                    towrite += towrite_link
                if(towrite_img):
                    towrite += towrite_img

                # get Last_Date

                if 'last-modified' in response.headers:
                    date = response.headers['Last-Modified']
                else:
                    date = response.headers['Date']

                date = datetime.datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %Z')

                towrite = towrite + "<lastmod>" + date.strftime('%Y-%m-%dT%H:%M:%S+00:00') + "</lastmod>" + "</url>"

                self.file_lock.acquire()
                self.output.write(towrite)
                self.file_lock.release()
                self.web_queue.task_done()



    def get_links(self,web_content):
        towrite_link = ""
        urls = self.urlregex.findall(web_content)

        for url in urls:
            if url.startswith('/'):
                url = self.domain + url
            elif not url.startswith("http"):
                url = self.domain + '/'+url

            if '#' in url:
                url = url[:url.index('#')]

            parsed_url = urlparse.urlparse(url)
            domain_url = "http://" + parsed_url.netloc

            # do not follow the external link
            if(url in self.excluded_url):
                continue
            elif(domain_url != self.domain):
                towrite_link = towrite_link + "<url><loc>"+self.unescape(url)+"</loc></url>"
                self.excluded_url.add(url)
                continue
            elif(url in self.crawled_webs):
                continue
            elif(url in self.web_queue.queue):
                continue
            # check dead link
            elif('javascript' in url):
                continue

            if(self.has_robot):
                if(not self.robot_parser.can_fetch('*',url)):
                    self.excluded_url.add(url)
                    continue
                else:
                    self.web_queue.put(url)
            else:
                self.web_queue.put(url)

        return towrite_link


    def get_imgs(self,web_content):
        towrite_img = ""
        imgregex = re.compile('<img [^>]*src=[\'|"].*?[\'|"].*? />')
        imgs = imgregex.findall(web_content)
        imgsrc = re.compile('src=[\'|"](.*?)[\'|"]')
        imgname = re.compile('alt=[\'|"](.*?)[\'|"]')
        for img in imgs:
            src = imgsrc.findall(img)
            if src[0].startswith('/'):
                src[0] = self.domain + src[0]
            else:
                continue
            alt = imgname.findall(img)
            alt = alt[0] if len(alt) else ""
            towrite_img = towrite_img + '<image:image><image:loc>'+ src[0] + '</image:loc>'
            towrite_img = towrite_img + '<image:title>'+alt+'</image:title>'+ '</image:image>'
            return towrite_img

    def unescape(self,s):
        # s = re.sub("<","&lt;"s)
        # s = re.sub(">","&gt;",s)
        if not re.match("&amp",s):
            s = re.sub("&","&amp;", s)
        return s

if __name__ == "__main__":
    if (len(sys.argv) < 2):
        raise ("Input domain")
    wc = web_crawler(domain=sys.argv[1])
    wc.run()
