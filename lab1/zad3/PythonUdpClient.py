import socket;

serverIP = "127.0.0.1"
serverPort = 9010
msg_bytes = (300).to_bytes(4, byteorder='little')

print('PYTHON UDP CLIENT')
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.sendto(msg_bytes, (serverIP, serverPort))

buff, _ = client.recvfrom(4)
nb = int.from_bytes(buff, byteorder='little')
print('received msg: ' + str(nb))
client.close()

