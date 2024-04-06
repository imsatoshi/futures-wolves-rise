from requests import get
from keep_alive import keep_alive

keep_alive()

ip = get('https://api.ipify.org').content.decode('utf8')
print('My public IP address is: {}'.format(ip))