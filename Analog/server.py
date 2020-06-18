import gc
import micropython
import usocket as socket
from ucollections import deque
import uselect as select
from machine import Pin
import dht


class ESPServer():
   
    def __init__(self,temper_threshold=20):
       
        self.tasks=deque( () , 20)

        self.poller=select.poll()

        self.wait={}

        self.mail_sent=0        
        self.threshold=temper_threshold
        self.sensor=dht.DHT11(Pin(2))  
        try:
            self.sensor.measure()
            self.temp=self.sensor.temperature()
            self.hum=self.sensor.humidity() 
 
            
        except:
            self.temp=0
            self.hum=0
            print("Can not measure")    

        self.tasks.append(self.micro_server())


    def run (self):      
    
        while self.tasks or self.wait:
            
            while not self.tasks:           
               
                new_request=self.poller.poll(1000)         
                
                if new_request:
                    
                    gc.collect()
                    for item,ev in new_request:
                        print('new request id = {} , item = {} with event = {} '.format(id(item),str(item)[0:15],ev ))
                        
                    print('Items in  wait list before delegating tasks')                        
                    for i,j in self.wait.items():                           
                        print('----key = {} val = {}'.format(i,str(j)[9:] )  )
                                              
                    for item in new_request:                       
                        print('trying to add task with item id = {}'.format(id(item[0])) )                            
                        self.tasks.append( self.wait.pop( id(item[0]) )   )
                   
                    print('Items in  wait list before delegating tasks') 
                    for i,j in self.wait.items():
                         
                          print('----key = {} val = {}'.format(i,str(j)[9:]))
              
                    gc.collect()

          
            task=self.tasks.popleft()     
        
            
            try:
                why,what=next(task)

                
                if why == 'recv':                  
                    self.poller.register( what , select.POLLIN )
                    self.wait[id(what)]=task
                    print('!Register a recv!- add to wait= id {} | socket = {} task = {} '.format( id(what),str(what)[8:15] ,str(task)[18:] ) )

                elif why == 'send':
                    self.poller.register( what , select.POLLOUT )
                    self.wait[id(what)]=task
                    print('!Register a send!- add to wait = id {}| socket = {} task = {}'.format(id(what),str(what)[8:15],str(task)[18:] ) )
                else:
                    raise RuntimeError        
            except StopIteration:
                print('task done')
                print('Items in  wait list after task completetion') 
                for i,j in self.wait.items():                    
                    print('----key = {} val = {}'.format(i,str(j)[9:]))
            




    def micro_server(self):    
        
        address=socket.getaddrinfo('0.0.0.0',25000,0,socket.SOCK_STREAM)[0][-1]
        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)    
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)    
        sock.bind(address)   
        sock.listen(15)
        
        
        while True:
            print('I am in server loop')
            yield 'recv',sock
        
            client_sock,addr=sock.accept()
            print('client connected {} , {}  serv.sock= {} cl.sock={}'.format( str(client_sock)[0:15] ,addr,id(sock),id(client_sock)  ) )
        
            self.poller.register(client_sock,select.POLLIN)
            self.wait[id(client_sock)]=self.req_handler(client_sock)
           
        
        

    def req_handler(self,client):
        
        while True:  
            
            print("I am in req handler with sock id ={} ".format( id(client) )  )
            
            yield 'recv',client

            try:
                req=client.recv(2048)
            except:
                print('CAN NOT RECV')
            
            
            print(req)
            
            if not req:
                self.poller.unregister(client)
                client.close()
                break 
            
            print(req[0:16])

            if req[0:11]==b'GET /my.css':             
                f=open('my.css','r')
                respond=f.read() 
                f.close()
                size=len(respond)
                print('size of file :{}'.format(size))
                header="HTTP/1.1 200 OK\r\n"+"Content-length: {}\r\n".format(size)+"Content-type: text/css;\r\n"+"Connection: keep-alive\r\n\r\n"
               

            elif req[0:8] == b'GET /ESP':
                gc.collect()
                
                
                self.temp=self.sensor.temperature()
                self.hum=self.sensor.humidity()   
                    
                
                f=open('index.html','r')
                temp=f.read()
                f.close()
                respond=temp % ( str(self.temp),str(self.hum) )
                size=len(respond)
                print('size of file :{}'.format(size))
                print( 'size of response is {}'.format(len(respond)) )
                header="HTTP/1.1 200 OK\r\n"+"cache-control: no-cache, private\r\n"+"Content-length: {}\r\n".format(size)+"Content-type: text/html; charset=UTF-8\r\n"+"Connection: keep-alive\r\n\r\n"
               
            elif req[0:20] == b'GET /%22/ESP/%22?ask':   
                gc.collect()             
               
                self.sensor.measure()
                self.temp=self.sensor.temperature()
                self.hum=self.sensor.humidity()

                respond='{"temp":'+str(self.temp)+',"hum":'+str(self.hum)+'}'           
                size=len(respond)
                print('size of file :{}'.format(size))
                print( 'size of response is {}'.format(len(respond)) )
                header="HTTP/1.1 200 OK\r\n"+"cache-control: no-cache, private\r\n"+"Content-length: {}\r\n".format(size)+"Content-type: text/html; charset=UTF-8\r\n"+"Connection: keep-alive\r\n\r\n"
                
           
            
            else:
                print(req[-5::1])                 
                respond=''
                size=0
                header="HTTP/1.1 404 NOT FOUND\r\n"+"cache-control: no-cache, private\r\n"+"Content-length: {}\r\n".format(size)+"Content-type: text/html; charset=UTF-8\r\n"+"Connection: close\r\n\r\n"   
                
                print('size of file :{}'.format(size))
                print( 'size of response is {}'.format(len(respond)) )             
                
                
            print("data recieved")     
            
#--------------------------------------------------------------------------------------------------    
            print("i am in write part with sock id = {}".format( id(client) )  )
            yield 'send',client       
            gc.collect()
            print('!!!!!trying sending data!!!!!!!')
            try:
                size_sent=client.write(header+respond ) 
                print("data sent!!!")
            except:
                size_sent=0
                print('CAN NOT SEND')         
            
            print('sent {} bytes of data'.format(size_sent))                                                                                           
            
        
        
            
            self.poller.unregister(client)

            
      

