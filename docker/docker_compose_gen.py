#!/usr/bin/python

head = '''
version: '2'
services:
'''

tail = '''
networks:
  app_net:
    driver: bridge
    ipam:
      driver: default
      config:
      - subnet: 172.16.238.0/24
        gateway: 172.16.238.1
'''

template = '''
  h%d:
    image: honeybadgerbft
    command: sh /start_multiple.sh
    networks:
      app_net:
        ipv4_address: 172.16.238.%d
    volumes:
      - ../../:/multi/
    environment:
      - LIBRARY_PATH=/usr/local/lib
      - LD_LIBRARY_PATH=/usr/local/lib
      - N=%d
      - t=%d
      - B=%d
      - MYSLEEP=%d
'''

def createDocker_compose(N, t, B, sleepTime = 1):
	if(N < 4 or N>253):
		raise Exception("Bad N.")
	res = head
	for i in range(N):
		res += template % (i+1, i+2, N, t, B, sleepTime)
	return res + tail

if __name__=="__main__":
	import sys
	print createDocker_compose(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))