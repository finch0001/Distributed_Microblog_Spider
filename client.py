__author__ = 'multiangle'
"""
    NAME:       client.py
    PY_VERSION: python3.4
    FUNCTION:   This client part of distrubuted microblog spider.
                The client request uid from server, and server
                return the list of uid whose info should be searched.
                After searching data, client will return data to
                server by POST method. If the data wanted to post
                is too large, it will be seperated into severl parts
                and transport individually
    VERSION:    _0.5_

"""
#======================================================================
#----------------import package--------------------------
# import python package
import urllib.request as request
import urllib.parse as parse
from multiprocessing import Process
import threading
import time
import os
import json
import http.cookiejar
import re
import random
from random import Random

# import from this folder
import client_config as config
import File_Interface as FI
#=======================================================================

#=======================================================================
#------------------code session--------------------------

class client():          # the main process of client
    def __init__(self):

        self.task_uid=None      #任务id
        self.task_type=None     #任务类型
        check_server()     #检查是否能连上服务器
        self.get_task()         #获取任务
        self.proxy_pool=[]
        self.get_proxy_pool(self.proxy_pool,config.PROXY_POOL_SIZE)
        self.run()

    def run(self):      # main code of the process
        # 监控proxy pool,建议get_proxy_pool单独开一个线程，
        # 如果server立即返回则马上关闭，否则设为长连接

        if self.task_type=='connect':
            sub_thread=getInfo(self.proxy_pool,self.task_uid)
        if self.task_type=='history':
            sub_thread=getHistory(self.proxy_pool,self.task_uid)
            #TODO 判断其他种类的task该做什么
        sub_thread.start()
        inner_count=0

        while True:
            inner_count+=1
            time.sleep(0.1)       #每隔0.1秒检查情况

            if inner_count==20:     # print the size of proxy pool
                print('client->run: the size of proxy pool is ',
                      self.proxy_pool.__len__())
                inner_count=0

            proxy_thread=get_proxy_pool_thread(self.proxy_pool,config.PROXY_POOL_SIZE)

            # if not proxy_thread.is_alive():         # maintain proxy pool
            #     if self.proxy_pool.__len__()<int(config.PROXY_POOL_SIZE/2):
            #         err_str='client->run : request proxy from server'
            #         info_manager(err_str)
            #         # proxy_thread=get_proxy_pool_thread(self.proxy_pool,config.PROXY_POOL_SIZE)
            #         proxy_thread.start()

            if self.proxy_pool.__len__()<int(config.PROXY_POOL_SIZE*2/3):
                err_str='client->run : request proxy from server'
                info_manager(err_str)
                self.get_proxy_pool(self.proxy_pool,config.PROXY_POOL_SIZE)

            if not sub_thread.is_alive():
                # self.return_proxy()
                break

    def get_task(self):

        """
        get task user id from server
        """

        url='{url}/task/?uuid={uuid}'.format(url=config.SERVER_URL,uuid=config.UUID)

        try:
            res=request.urlopen(url,timeout=10).read()
            res=str(res,encoding='utf8')
        except Exception as e:
            check_server()     # sleep until server is available
            try:
                res=request.urlopen(url,timeout=10).read()
                res=str(res,encoding='utf8')
            except:
                err_str='error: client -> get_task : ' \
                        'unable to connect to server, exit process'
                info_manager(err_str,type='KEY')
                os._exit(0)

        if 'no task' in res:       # if server have no task uid ,return 'no task uid'
            err_str= 'error: client -> get_task : ' \
                     'unable to get task, sleep for 1 min and exit process'
            info_manager(err_str,type='KEY')
            time.sleep(60)
            os._exit(0)

        try:        # try to parse task str
            res=res.split(',')
            self.task_uid=res[0]
            self.task_type=res[1]
        except:
            err_str='error: client -> get_task : ' \
                    'unable to split task str,exit process'
            info_manager(err_str,type='KEY')
            os._exit(0)

    def get_proxy_pool(self,proxy_pool,num):

        """
        request certain number of proxy from server
        :param num:
        :return: None, but a list of proxy as formation of [[proxy(str),timeout(float)]...[]]
                    will be added to self.proxy_pool
        """

        url='{url}/proxy/?num={num}'.format(url=config.SERVER_URL,num=num)

        try:
            res=request.urlopen(url,timeout=5).read()
            res=str(res,encoding='utf8')
        except:
            time.sleep(5)
            check_server()     # sleep until server is available
            try:
                res=request.urlopen(url,timeout=5).read()
                res=str(res,encoding='utf8')
            except Exception as e:
                err_str='error: client -> get_proxy_pool : unable to ' \
                        'connect to proxy server '
                info_manager(err_str,type='KEY')
                if config.KEY_INFO_PRINT:
                    print(e)
                return

        if 'no valid proxy' in res:     # if server return no valid proxy, means server
                                            # cannot provide proxy to this client
            err_str='error: client -> get_proxy_pool : fail to ' \
                    'get proxy from server'
            info_manager(err_str,type='KEY')
            time.sleep(1)
            return

        try:
            data=res.split(';')             # 'url,timedelay;url,timedelay;.....'
            data=[proxy_object(x) for x in data]
        except Exception as e:
            err_str='error: client -> get_proxy_pool : fail to ' \
                    'parse proxy str info:\r\n'+res
            info_manager(err_str,type='KEY')
            return

        proxy_pool[:]=proxy_pool[:]+data

    def return_proxy(self):

        """
        return useful or unused proxy to server
        """

        check_server()
        url='{url}/proxy_return'.format(url=config.SERVER_URL)
        proxy_ret= [x.raw_data for x in self.proxy_pool]
        proxy_str=''

        for item in proxy_ret:
            proxy_str=proxy_str+item
        data={
            'data':proxy_str
        }

        data=parse.urlencode(data).encode('utf-8')

        try:
            opener=request.build_opener()
            req=request.Request(url,data)
            res=opener.open(req).read().decode('utf-8')
        except:
            try:
                opener=request.build_opener()
                req=request.Request(url,data)
                res=opener.open(req).read().decode('utf-8')
            except:
                err_str='error:client->return_proxy:unable to ' \
                        'connect to server'
                info_manager(err_str,type='KEY')
                return

        if 'return success' in res:
            print('Success: return proxy to server')
            return
        else:
            err_str='error:client->return_proxy:'+res
            info_manager(err_str,type='KEY')
            # raise ConnectionError('Unable to return proxy')
            return

class get_proxy_pool_thread(threading.Thread):
    def __init__(self,proxy_pool,num):
        threading.Thread.__init__(self)
        self.proxy_pool=proxy_pool
        self.num=num

    def run(self):
        url='{url}/proxy/?num={num}'.format(url=config.SERVER_URL,num=self.num)

        try:
            res=request.urlopen(url,timeout=5).read()
            res=str(res,encoding='utf8')
        except:
            time.sleep(5)
            check_server()     # sleep until server is available
            try:
                res=request.urlopen(url,timeout=5).read()
                res=str(res,encoding='utf8')
            except Exception as e:
                err_str='error: get_proxy_pool_thread -> run : ' \
                        'unable to connect to proxy server '
                info_manager(err_str,type='KEY')
                if config.KEY_INFO_PRINT:
                    print(e)
                return

        if 'no valid proxy' in res:     # if server return no valid proxy, means server
            # cannot provide proxy to this client
            err_str='error: client -> get_proxy_pool : fail to ' \
                    'get proxy from server'
            info_manager(err_str,type='KEY')
            time.sleep(1)
            return

        try:
            data=res.split(';')             # 'url,timedelay;url,timedelay;.....'
            data=[proxy_object(x) for x in data]
        except Exception as e:
            err_str='error: client -> get_proxy_pool : fail to ' \
                    'parse proxy str info:\r\n'+res
            info_manager(err_str,type='KEY')
            return

        self.proxy_pool[:]=self.proxy_pool[:]+data

class getInfo(threading.Thread):       # 用来处理第一类任务，获取用户信息和关注列表

    def __init__(self,proxy_pool,uid):
        threading.Thread.__init__(self)
        self.conn=Connector(proxy_pool,if_proxy=False)      #请求用户基本信息的时候会暂时关掉proxy
        self.uid=uid
        self.proxy_pool=proxy_pool

    def run(self):
        time.sleep(max(0.1,random.gauss(1,0.2)))
        self.user_basic_info=self.getBasicInfo()
        self.attends=self.getAttends(self.user_basic_info['container_id'],
                                     self.proxy_pool)
        userInfo={
            'user_basic_info':self.user_basic_info,
            'user_attends':self.attends
        }

        try:
            data=parse.urlencode(userInfo).encode('utf8')
        except:
            err_str='error:getInfo->run: ' \
                    'unable to parse uesr info data'
            info_manager(err_str,type='KEY')
            raise TypeError('Unable to parse user info')

        url='{url}/info_return'.format(url=config.SERVER_URL)
        req=request.Request(url,data)
        opener=request.build_opener()

        try:
            res=opener.open(req)
        except:
            times=0

            while times<5:
                times+=1
                time.sleep(3)
                try:
                    res=opener.open(req)
                    break
                except:
                    warn_str='warn:getInfo->run:' \
                             'unable to return info to server ' \
                             'try {num} times'.format(num=times)
                    info_manager(warn_str,type='NORMAL')
            if times==5:
                FI.save_pickle(self.attends,'data.pkl')
                string='warn: getInfo->run: ' \
                        'get attends list, but unable to connect server,' \
                        'stored in data.pkl'
                info_manager(string,type='KEY')

        res=res.read().decode('utf8')
        if 'success to return user info' in res:
            suc_str='Success:getInfo->run:' \
                    'Success to return user info to server'
            info_manager(suc_str,type='KEY')
        else:
            FI.save_pickle(userInfo,'data.pkl')
            string='warn: getInfo->run: ' \
                   'get attends list, but unable to connect server,' \
                   'stored in data.pkl'
            info_manager(string,type='KEY')

        self.return_proxy()
        #注意是否要将信息分开发送
        os._exit(0)

    def return_proxy(self):

        """
        return useful or unused proxy to server
        """

        # check_server()
        url='{url}/proxy_return'.format(url=config.SERVER_URL)
        proxy_ret= [x.raw_data for x in self.proxy_pool]
        proxy_str=''

        for item in proxy_ret:
            proxy_str=proxy_str+item+';'
        proxy_str=proxy_str[0:-1]
        data={
            'data':proxy_str
        }

        data=parse.urlencode(data).encode('utf-8')

        try:
            opener=request.build_opener()
            req=request.Request(url,data)
            res=opener.open(req).read().decode('utf-8')
        except:
            try:
                opener=request.build_opener()
                req=request.Request(url,data)
                res=opener.open(req).read().decode('utf-8')
            except:
                err_str='error:client->return_proxy:unable to ' \
                        'connect to server'
                info_manager(err_str,type='KEY')
                return

        if 'return success' in res:
            print('Success: return proxy to server')
            return
        else:
            err_str='error:client->return_proxy:'+res
            info_manager(err_str,type='KEY')
            # raise ConnectionError('Unable to return proxy')
            return

    def getBasicInfo(self):
        """
        get user's basic information,
        :param uid:
        :return:basic_info(dict)
        """
        homepage_url = 'http://m.weibo.cn/u/' + str(self.uid)

        try:
            homepage_str = self.conn.getData(homepage_url)
        except :
            raise ConnectionError('Unable to get basic info')

        user_basic_info={}
        info_str = re.findall(r'{(.+?)};', homepage_str)[1].replace("'", "\"")
        info_str = '{'+ info_str +'}'
        print(info_str)
        info_json = json.loads(info_str)


        user_basic_info['container_id'] = info_json['common']['containerid']     #containerid
        info = json.loads(info_str)['stage']['page'][1]
        user_basic_info['uid'] = info['id']                                         #uid
        user_basic_info['name'] = info['name']                                     #name
        user_basic_info['description'] = info['description']                     #description
        user_basic_info['gender'] = ('male' if info['ta'] == '他' else 'female')   #sex
        user_basic_info['verified'] = info['verified']
        user_basic_info['verified_type'] = info['verified_type']
        user_basic_info['native_place'] = info['nativePlace']

        user_basic_info['fans_num'] = info['fansNum']
        if isinstance(info['fansNum'],str):
            temp=info['fansNum'].replace('万','0000')
            temp=int(temp)
            user_basic_info['fans_num']=temp

        user_basic_info['blog_num'] = info['mblogNum']
        if isinstance(info['mblogNum'],str):
            temp=info['mblogNum'].replace('万','0000')
            temp=int(temp)
            user_basic_info['blog_num']=temp

        user_basic_info['attends_num'] = info['attNum']
        if isinstance(info['attNum'],str):
            temp=info['attNum'].replace('万','0000')
            temp=int(temp)
            user_basic_info['attends_num']=temp

        user_basic_info['detail_page']="http://m.weibo.cn/users/"+str(user_basic_info['uid'])
        user_basic_info['basic_page']='http://m.weibo.cn/u/'+str(user_basic_info['uid'])
        print('\n','CURRENT USER INFO ','\n','Name:',user_basic_info['name'],'\t','Fans Num:',user_basic_info['fans_num'],'\t',
              'Attens Num:',user_basic_info['attends_num'],'\t','Blog Num:',user_basic_info['blog_num'],'\n',
              'Atten Page Num:',int(user_basic_info['attends_num']/10),'\n',
              'description:',user_basic_info['description']
        )
        return user_basic_info

    def getAttends(self,container_id,proxy_pool):

        attends_num=self.user_basic_info['attends_num']
        model_url='http://m.weibo.cn/page/tpl?containerid='\
                  +str(container_id)+'_-_FOLLOWERS&page={page}'
        page_num=int(attends_num/10)
        task_url=[model_url.format(page=(i+1)) for i in range(page_num)]
        random.shuffle(task_url)            # 对任务列表进行随机排序
        attends=[]
        threads_pool=[]                     #线程池
        for i in range(config.THREAD_NUM):  # thread initialization
            t=self.getAttends_subThread(task_url,proxy_pool,attends)
            threads_pool.append(t)
        for t in threads_pool:              # thread_list
            t.start()

        while True:
            time.sleep(0.2)
            if task_url :   # 如果 task_url 不为空，则检查是否有进程异常停止
                for i in range(config.THREAD_NUM):
                    if not threads_pool[i].is_alive() :
                        threads_pool[i]=self.getAttends_subThread(task_url,proxy_pool,attends)
                        threads_pool[i].start()
            else:           #如果 task_url 为空，则当所有线程停止时跳出
                all_stoped=True
                for t in threads_pool:
                    if t.is_alive():
                        all_stoped=False
                if all_stoped:
                    break
        attends_unique=[]
        attends_uid=[]
        for i in range(attends.__len__()):
            if attends[i]['uid'] not in attends_uid:
                attends_uid.append(attends[i]['uid'])
                attends_unique.append(attends[i])
            else:
                pass
        return attends_unique

    class getAttends_subThread(threading.Thread):

        def __init__(self,task_url,proxy_pool,attends):
            threading.Thread.__init__(self)
            self.task_url=task_url
            self.conn=Connector(proxy_pool)
            self.attends=attends

        def run(self):
            while True:
                if not self.task_url:
                    break
                url=self.task_url.pop(0)
                time.sleep(max(random.gauss(0.5,0.1),0.05))
                try:
                    page=self.conn.getData(url,
                                           timeout=10,
                                           reconn_num=2,
                                           proxy_num=30)
                except Exception as e:
                    print('error:getAttends_subThread->run: '
                          'fail to get page'+url)
                    print('skip this page')
                    # self.task_url.append(url)
                    continue
                page='{\"data\":['+page[1:]+'}'
                try:
                    page=json.loads(page)
                    page=page['data'][1]
                    temp_list=[card_group_item_parse(x) for x in page['card_group']]
                    self.attends[:]=self.attends[:]+temp_list
                    info_str='Success: Page {url} is done'.format(url=url)
                    info_manager(info_str,type='NORMAL')
                except Exception as e:
                    try:                #分析是否是因为 “没有内容” 出错，如果是，当前的应对措施是休眠5秒，再次请求。
                        # page=page.replace(' ','')
                        data=json.loads(page)
                        if data['test'][1]['msg']=='没有内容':
                            time.sleep(5)
                            print('--- fail to get valid page, sleep for 5 seconds ---')
                            try:
                                page = self.conn.getData(url,
                                                         timeout=10,
                                                         reconn_num=2,
                                                         proxy_num=30)
                            except Exception as e:
                                print('error:getAttends_subThread->run: '
                                      'fail to get page twice:'+url)
                                print('skip this page')
                                continue
                            try:
                                page='{\"data\":['+page[1:]+'}'
                                page=json.loads(page)
                                page=page['data'][1]
                                # page=re.findall(r'"card_group":.+?]}]',page)[0]
                                # page='{'+page[:page.__len__()-1]
                                # page=json.loads(page)
                                temp_list=[card_group_item_parse(x) for x in page['card_group']]
                                self.attends[:]=self.attends[:]+temp_list
                                info_str='Success: Page {url} is done'.format(url=url)
                                info_manager(info_str,type='KEY')
                            except:
                                print(e)
                                pass    #如果再次失败，当前措施是直接跳过
                    except Exception as e:  #如果不是因为 “没有内容出错” 则出错原因不明，直接跳过
                        if config.KEY_INFO_PRINT: print(e)
                        err_str='error:getAttends_subThread->run:Unknown page type, ' \
                                'fail to parse {url}'.format(url=url)
                        info_manager(err_str,type='NORMAL')
                        if config.NOMAL_INFO_PRINT: print(page)
                        if config.NOMAL_INFO_PRINT: print('--- skip this page ---')
                        pass

def card_group_item_parse(sub_block):

        """
        :param user_block   : json type
        :return:  user      : dict type
        """

        user_block=sub_block['user']
        user_block_keys=user_block.keys()
        user={}

        if 'profile_url' in user_block_keys:
            user['basic_page']=user_block['profile_url']

        if 'screen_name' in user_block_keys:
            user['name']=user_block['screen_name']

        if 'desc2' in user_block_keys:
            user['recent_update_time']=user_block['desc2']

        if 'desc1' in user_block_keys:
            user['recent_update_content']=user_block['desc1']

        if 'gender' in user_block_keys:
            user['gender']=('male' if user_block['gender']=='m' else 'female')

        if 'verified_reason' in user_block_keys:
            user['verified_reason']=user_block['verified_reason']

        if 'profile_image_url' in user_block_keys:
            user['profile']=user_block['profile_image_url']

        if 'statuses_count' in user_block_keys:
            temp=user_block['statuses_count']
            if isinstance(temp,str):
                temp=int(temp.replace('万','0000'))
            user['blog_num']=temp

        if 'description' in user_block_keys:
            user['description']=user_block['description']

        if 'follow_me' in user_block_keys:
            user['follow_me']=user_block['follow_me']

        if 'id' in user_block_keys:
            user['uid']=user_block['id']

        if 'fansNum' in user_block_keys:
            temp=user_block['fansNum']
            if isinstance(temp,str):
                temp=int(temp.replace('万','0000'))
            user['fans_num']=temp

        return user

def check_server():

    """
    check if server can provide service
    if server is valid, will return 'connection valid'
    """

    url='{url}/auth'.format(url=config.SERVER_URL)
    while True:

        try:
            res=request.urlopen(url,timeout=5).read()
            res=str(res,encoding='utf8')
            if 'connection valid' in res:
                break
            else:
                error_str='error: client-> check_server :' \
                          'no auth to connect to server,exit process'
                info_manager(error_str,type='KEY')
                os._exit(0)
        except Exception as e:
            err_str='error:client->check_server:cannot ' \
                    'connect to server; process sleeping'
            info_manager(err_str,type='NORMAL')
            print(e)
            time.sleep(5)       # sleep for 1 seconds

class Connector():
    def __init__(self,proxy_pool,if_proxy=True):      #从proxy_pool队列中取出一个
        self.headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) '
                                       'AppleWebKit/600.1.3 (KHTML, like Gecko) Version/8.0 Mobile'
                                       '/12A4345d Safari/600.1.4'}
        self.proxy_pool=proxy_pool
        self.cj=http.cookiejar.CookieJar()
        self.if_proxy=if_proxy

        if if_proxy :
            counting=0

            while True:

                try:
                    self.current_proxy_oj=proxy_pool.pop(0)
                    break
                except:
                    time.sleep(1)
                    counting+=1
                    if counting>60:
                        raise ConnectionError('unable to get proxy')

            self.proxy_handler=request.ProxyHandler({'http':self.current_proxy_oj.url})
            # self.opener=request.build_opener(request.HTTPCookieProcessor(self.cj),self.proxy_handler)
            self.opener=request.build_opener(self.proxy_handler)
        else:
            self.current_proxy_oj=None
            self.opener=request.build_opener(request.HTTPCookieProcessor(self.cj))
        request.install_opener(self.opener)

    def getData(self,url,timeout=10,reconn_num=2,proxy_num=30):
        try:
            res=self.getData_inner(url,timeout=timeout)
            return res
        except Exception as e:
            err_str='warn: Connector->getData : connect fail,ready to connect'
            info_manager(err_str,type='NORMAL')
            if config.NOMAL_INFO_PRINT: print(e)
            proxy_count=1
            while(proxy_count<=proxy_num):
                reconn_count=1
                while(reconn_count<=reconn_num):
                    time.sleep(max(random.gauss(2,0.5),0.5))
                    err_str='warn: Connector->getData:the {num}th reconnect  '.format(num=reconn_count)
                    info_manager(err_str,type='NORMAL')
                    try:
                        res=self.getData_inner(url,timeout=timeout)
                        return res
                    except:
                        reconn_count+=1
                info_manager('warn: Connector->getData:reconnect fail, ready to change proxy',type='NORMAL')
                self.change_proxy()
                err_str='warn: Connector->getData:change proxy for {num} times'.format(num=proxy_count)
                info_manager(err_str,type='NORMAL')
                proxy_count+=1
            raise ConnectionError('run out of reconn and proxy times')

    def getData_inner(self,url,timeout=10):
        # if self.if_proxy:
        #     opener=request.build_opener(request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        #                                 request.ProxyHandler({'http':self.current_proxy_oj.url}))
        # else:
        #     opener=request.build_opener(request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

        req=request.Request(url,headers=self.headers)
        # request.install_opener(opener)
        result=self.opener.open(req,timeout=timeout)
        # result=opener.open(req,timeout=timeout)
        return result.read().decode('utf-8')

    def change_proxy(self,retry_time=50):
        try:
            self.current_proxy_oj=self.proxy_pool.pop(0)
        except Exception as e:
            print(e)
            re_try=1
            while(re_try<retry_time):
                time.sleep(5)
                try:
                    self.current_proxy_oj=self.proxy_pool.pop(0)
                    break
                except:
                    err_str='warn: Connector->change_proxy:' \
                            're_try fail,ready to try again' \
                            ' size of proxy pool is {num}'\
                        .format(num=self.proxy_pool.size())
                    info_manager(err_str,type='NORMAL')
                    re_try+=1
            if re_try==retry_time: raise ConnectionError('Unable to get proxy from proxy_pool')
        self.cj=http.cookiejar.CookieJar()
        self.proxy_handler=request.ProxyHandler({'http':self.current_proxy_oj.url})
        self.opener=request.build_opener(request.HTTPCookieProcessor(self.cj),
                                         self.proxy_handler)
        request.install_opener(self.opener)

class proxy_object():
    def __init__(self,data):    # in this version ,data is in formation of [str(proxy),int(timedelay)]
        self.raw_data=data
        res=data.split(',')
        self.url=res[0]
        self.timedelay=res[1]
    def getUrl(self):
        return self.url
    def getRawType(self):       #返回原来格式
        return self.raw_data

def info_manager(info_str,type='NORMAL'):
    time_stick=time.strftime('%Y/%m/%d %H:%M:%S ||', time.localtime(time.time()))
    str=time_stick+info_str
    if type=='NORMAL':
        if config.NOMAL_INFO_PRINT:
            print(str)
    if type=='KEY':
        if config.KEY_INFO_PRINT:
            print(str)

class getHistory(threading.Thread):

    def __init__(self,proxy_pool,task_uid):
        threading.Thread.__init__(self)
        task_uid=task_uid.split(';')
        self.container_id=task_uid[0]
        self.blog_num=task_uid[1]
        self.proxy_pool=proxy_pool

    def run(self):

        model_url='http://m.weibo.cn/page/json?containerid='\
                  +str(self.container_id)+\
                  '_-_WEIBO_SECOND_PROFILE_WEIBO&page={page}'
        page_num=int(int(self.blog_num)/10)
        task_url=[model_url.format(page=(i+1)) for i in range(page_num)]
        random.shuffle(task_url)
        contents=[]
        threads_pool=[]
        for i in range(config.THREAD_NUM):  # thread initialization
            t=self.getHistory_subThread(task_url,self.proxy_pool,contents)
            threads_pool.append(t)
        for t in threads_pool:
            t.start()

        while True:
            time.sleep(0.2)
            if task_url:    # if task url not null, check if all thread is working
                for i in range(config.THREAD_NUM):
                    if not threads_pool[i].is_alive():
                        threads_pool[i]=self.getHistory_subThread(
                            task_url,self.proxy_pool,contents)
                        threads_pool[i].start()
            else:       # if task is void ,exit if all subthread is stoped
                all_stoped=True
                for t in threads_pool:
                    if t.is_alive():
                        all_stoped=False
                if all_stoped:
                    break

        content_unique=[]      # pick out the repeated content
        content_msgid=[]
        for i in range(contents.__len__()):
            if contents[i]['msg_id'] not in content_msgid:
                content_msgid.append(contents[i]['msg_id'])
                content_unique.append(contents[i])
            else:
                pass

        # for test
        #todo to delete
        model_name='F:\\multiangle\\Coding!\\python\\' \
                   'Distributed_Microblog_Spider\\{id}.pkl'\
            .format(id=self.container_id)
        FI.save_pickle(content_unique,model_name)
        print('user {id} is fetched, saved'.format(id=self.container_id))
        #


        userHistory={           # return the user's history to server
            'user_history':content_unique
        }
        try:
            data=parse.urlencode(userHistory).encode('utf8')
        except:
            err_str='error:getHistory->run: ' \
                    'unable to parse uesr history data'
            info_manager(err_str,type='KEY')
            raise TypeError('Unable to parse user history')

        url='{url}/history_return'.format(url=config.SERVER_URL)
        req=request.Request(url,data)
        opener=request.build_opener()

        try:
            res=opener.open(req)
        except:
            times=0

            while times<5:
                times+=1
                time.sleep(3)
                try:
                    res=opener.open(req)
                    break
                except:
                    warn_str='warn:getHistory->run:' \
                             'unable to return history to server ' \
                             'try {num} times'.format(num=times)
                    info_manager(warn_str,type='NORMAL')
            if times==5:
                FI.save_pickle(contents,'data.pkl')
                string='warn: getHistory->run: ' \
                       'get user history , but unable to connect server,' \
                       'stored in data.pkl'
                info_manager(string,type='KEY')

        res=res.read().decode('utf8')
        if 'success to return user history'in res:
            suc_str='Success:getHistory->run:' \
                    'Success to return user history to server'
            info_manager(suc_str,type='KEY')
        else:
            FI.save_pickle(contents,'data.pkl')
            string='warn: getHistory->run: ' \
                   'get user history, but unable to connect server,' \
                   'stored in data.pkl'
            info_manager(string,type='KEY')

        self.return_proxy()

        os._exit(0)

    def return_proxy(self):

        """
        return useful or unused proxy to server
        """

        # check_server()
        url='{url}/proxy_return'.format(url=config.SERVER_URL)
        proxy_ret= [x.raw_data for x in self.proxy_pool]
        proxy_str=''

        for item in proxy_ret:
            proxy_str=proxy_str+item+';'
        proxy_str=proxy_str[0:-1]
        data={
            'data':proxy_str
        }

        data=parse.urlencode(data).encode('utf-8')

        try:
            opener=request.build_opener()
            req=request.Request(url,data)
            res=opener.open(req).read().decode('utf-8')
        except:
            try:
                opener=request.build_opener()
                req=request.Request(url,data)
                res=opener.open(req).read().decode('utf-8')
            except:
                err_str='error:client->return_proxy:unable to ' \
                        'connect to server'
                info_manager(err_str,type='KEY')
                return

        if 'return success' in res:
            print('Success: return proxy to server')
            return
        else:
            err_str='error:client->return_proxy:'+res
            info_manager(err_str,type='KEY')
            # raise ConnectionError('Unable to return proxy')
            return

    class getHistory_subThread(threading.Thread):

        def __init__(self,task_url,proxy_pool,contents):
            threading.Thread.__init__(self)
            self.task_url=task_url
            self.proxy_pool=proxy_pool
            self.contents=contents
            self.conn=Connector(proxy_pool)

        def run(self):
            while True:
                if not self.task_url:
                    break
                url=self.task_url.pop(0)
                time.sleep(max(random.gauss(0.5,0.1),0.05))
                try:
                    page=self.conn.getData(url,
                                           timeout=10,
                                           reconn_num=2,
                                           proxy_num=30)
                except Exception as e:
                    print('error:getHistory_subThread->run: '
                          'fail to get page'+url)
                    print('skip this page')
                    continue

                try:
                    res=parse_blog_page(page)
                    # TODO DELETE for test--------
                    for i in res:
                        print(json.dumps(i,indent=4))
                    #---------------------------------
                    self.contents[:]=self.contents[:]+res
                    info_str='Success: Page {url} is done'.format(url=url)
                    info_manager(info_str,type='NORMAL')
                except Exception as e:
                    info_str='error: getHistory_subThread->run: ' \
                            'fail to parse {url}'.format(url=url)
                    info_manager(info_str,type='KEY')
                    print(e)

def parse_blog_page(data):
    try:        # check if the page is json type
        data=json.loads(data)
    except:
        save_page(data)
        raise ValueError('Unable to parse page')

    try:        # check if the page is empty
        mod_type=data['cards'][0]['mod_type']
    except:
        save_page(json.dumps(data))
        raise ValueError('The type of this page is incorrect')

    # debug
    #TODO to delete
    temp_name=random_str(randomlength=15)
    base_dir='F:\\multiangle\\Coding!\\python\\Distribut' \
            'ed_Microblog_Spider\\html_page\\'
    path=base_dir+temp_name+'.pkl'
    FI.save_pickle(data,path)
    # debug


    if 'empty' in mod_type:
        raise ValueError('This page is empty')

    try:        # get card group as new data
        data=data['cards'][0]['card_group']
    except:
        save_page(json.dumps(data))
        raise ValueError('The type of this page is incorrect')

    data_list=[]
    for block in data:
        res=parse_card_group(block)
        data_list.append(res)

    return data_list
    # for item in data_list:
    #     print(json.dumps(item,indent=4))

def temp_page_parser(data):  #用来测试网页对应内容的临时程序
    #data 是一个字典格式
    keys=list(data.keys())
    msg={}
    key_array=[
        'created_at',               #信息创建时间
        'attitudes_count',          #点赞数
        'mlevel',            #不明
        'biz_feature',      #不明
        'biz_ids',          #不明
        'source_type',      #不明
        'hot_weibo_tags',  #不明
        'isLongText',               #是否是长微博
        'original_pic',             #图片相关，似乎相关信息可以在pic中找到
        'mblogtype',        #不明
        'idstr',                    #等同于id，是str形式
        'pic_ids',                  #图片id
        'visible',          #不明
        'bmiddle_pic',      #不明
        'pics',                     #如果包含图的话，有该项，包括size,pid,geo,url等
        'mid',                      #等同于id
        'pid',               #不明
        'userType',         #不明
        'thumbnail_pic',            #地址似乎等于pic中图片地址
        'favorited',        #不明
        'attitudes_status',#不明
        'bid',               #不明
        'page_type',        #不明
        'textLength',               #文本长度
        'source',           #不明
        'source_allowclick',#不明
        'expire_time',      #不明
        'extend_info',      #不明，不过似乎没什么用
        'mark',              #不明
        'id',                        #信息id
        'text',                      #文本信息
        'reposts_count',            #转发数
        'comments_count',           #评论数目
        'like_count',               #点赞数目
        'created_timestamp',        #创建时间戳
        'source_type',      #不明
        'cardid',          #不明，应该是显示账号等级的，如star_003等等
        'retweeted_status',         #转发相关
        'url_struct',        #不明，字典形式
        'topic_struct',     #不明，似乎是topic结构，是字典 形式
        'page_info'          #不太明，似乎与多媒体有关，字典形式
    ]
    for item in key_array:
        if item in keys:
            msg[item]=data[item]
    all_in=True
    for item in keys:
        if item not in key_array:
            if item!='text' and item!='user' :
                all_in=False
                break
    if not all_in:
        temp_name=random_str(randomlength=15)
        base_dir='F:\\multiangle\\Coding!\\python\\Distribut' \
                 'ed_Microblog_Spider\\html_page\\'
        path=base_dir+temp_name+'.pkl'
        FI.save_pickle(data,path)

    if 'text' in keys:
        msg['content']=data['text']
    if 'user' in keys:
        msg['user']=parse_user_info(data['user'])

def parse_card_group(data):
    data=data['mblog']
    temp_page_parser(data)
    msg=parse_card_inner(data)
    return msg

def parse_card_inner(data):
    msg={}
    keys=list(data.keys())
    if 'id' in keys:
        msg['msg_id']=data['idstr']
    if 'text' in keys:
        msg['content']=data['text']
    if 'created_at' in keys:
        msg['time']=data['created_at']
    if 'reposts_count' in keys:
        msg['reposts_count']=data['reposts_count']
    if 'comments_count' in keys:
        msg['comments_count']=data['comments_count']
    if 'like_count' in keys:
        msg['like_count']=data['like_count']
    if 'created_timestamp' in keys:
        msg['time_stamp']=data['created_timestamp']
    if 'user' in keys:
        msg['user']=parse_user_info(data['user'])
    if 'retweeted_status' in keys:
        msg['is_retweeted']=True
        msg['retweeted_info']=parse_card_inner(data['retweeted_status'])
    else:
        msg['is_retweeted']=False
    return msg
    #todo  需要处理的内容：text,retweeted,topic_struct,url_struct,page_info

def parse_text(text_data):
    pass

def parse_user_info(user_data):
    keys=user_data.keys()
    user={}
    if 'id' in keys:
        user['uid']=user_data['id']
    if 'screen_name' in keys:
        user['name']=user_data['screen_name']
    if 'profile_url' in keys:
        user['user_page']=user_data['profile_url']
    if 'description' in keys:
        user['description']=user_data['description']
    if 'fansNum' in keys:
        user['fans_num']=user_data['fansNum']
    return user

def random_str(randomlength=8):
    str = ''
    chars = 'AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz0123456789'
    length = len(chars) - 1
    random = Random()
    for i in range(randomlength):
        str+=chars[random.randint(0, length)]
    return str

def save_page(page):
    pass
    #TODO 未完成

if __name__=='__main__':
    p_pool=[]
    for i in range(config.PROCESS_NUM):
        p=Process(target=client,args=())
        p_pool.append(p)
    for p in p_pool:
        p.start()

    while True:
        for i in range(p_pool.__len__()):
            if not p_pool[i].is_alive():
                p_pool[i]=Process(target=client,args=())
                x=random.randint(1,10)
                time.sleep(x)
                p_pool[i].start()


