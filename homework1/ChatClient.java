package zad1;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.MulticastSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.Scanner;


public class ChatClient {
    private static final String SERVER_HOST = "127.0.0.1";
    private static final int SERVER_PORT = 12345;

    private static final String MULTICAST_GROUP = "230.0.0.1";
    private static final int MULTICAST_PORT = 12346;

    private static final int BUFFER_SIZE = 1024;

    private String localUsername;

    private volatile boolean running = true;

    public static void main(String[] args) {
        new ChatClient().start();
    }

    public void start() {
        Scanner scanner = new Scanner(System.in);
        System.out.print("Enter your username: ");
        String username = scanner.nextLine();
        localUsername = username;

        try(
            Socket tcpSocket = new Socket(SERVER_HOST, SERVER_PORT);
            PrintWriter writer = new PrintWriter(tcpSocket.getOutputStream(), true, StandardCharsets.UTF_8);
            BufferedReader reader = new BufferedReader(new InputStreamReader(tcpSocket.getInputStream(), StandardCharsets.UTF_8));       
        ) {

            writer.println(username);

            String response = reader.readLine();
            if (!"OK".equals(response)){
                System.out.println(response);
                return;
            }

            int localPort = tcpSocket.getLocalPort();

            try(
                DatagramSocket udpSocket = new DatagramSocket(localPort);
                MulticastSocket multicastSocket = new MulticastSocket(MULTICAST_PORT);
            ){
                registerUdp(username, udpSocket);
                
                InetAddress multicastAddress = InetAddress.getByName(MULTICAST_GROUP);
                java.net.SocketAddress group = new java.net.InetSocketAddress(multicastAddress, MULTICAST_PORT);
                java.net.NetworkInterface networkInterface = java.net.NetworkInterface.getByInetAddress(InetAddress.getLocalHost());
                multicastSocket.joinGroup(group, networkInterface);

                Thread tcpListener = new Thread(() -> listenTcp(reader));
                Thread udpListener = new Thread(() -> listenUdp(udpSocket));
                Thread multicastListener = new Thread(() -> listenMulticast(multicastSocket));

                tcpListener.setDaemon(true);
                udpListener.setDaemon(true);
                multicastListener.setDaemon(true);

                tcpListener.start();
                udpListener.start();
                multicastListener.start();

                System.out.println("Connected to chat server.");
                System.out.println("TCP port: " + localPort);
                System.out.println("UDP port: " + udpSocket.getLocalPort());
                System.out.println("Multicast group: " + MULTICAST_GROUP);
                System.out.println("Type message to send a message using TCP.");
                System.out.println("Type U to send a message using UDP.");
                System.out.println("Type M to send a message using Multicast.");
                System.out.println("Type exit to quit.");

                while (true) {
                    String message = scanner.nextLine();

                    if (message.equalsIgnoreCase("exit")) {
                        running = false;
                        break;
                    } else if(message.equalsIgnoreCase("U")) {
                        System.out.print("Enter message to send via UDP \n(Finish message with line: END):\n");
                        String udpMessage = readMultilineMessage(scanner);
                        sendUdpMessage(username, udpMessage, udpSocket);
                        continue;
                    } else if (message.equalsIgnoreCase("M")) {
                        System.out.print("Enter message to send via Multicast \n(Finish message with line: END):\n");
                        String multicastMessage = readMultilineMessage(scanner);
                        sendMulticastMessage("MCAST:" + username + ": " + multicastMessage, multicastSocket, multicastAddress);
                    } else {
                        writer.println(message);
                    }
                } 
                tcpSocket.close();
                udpSocket.close();
                multicastSocket.close();
            }

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void listenTcp(BufferedReader reader) {
        try {
            String message;
            while ((message = reader.readLine()) != null) {
                System.out.println(message);
            }
        } catch (Exception e) {
            if (running && e.getMessage() != null){
                System.out.println(e.getMessage());
            }
        }
    }

    private void listenUdp(DatagramSocket socket) {
        try {
            while (true) {
                byte[] buffer = new byte[BUFFER_SIZE];
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                socket.receive(packet);
                String message = new String(packet.getData(), packet.getOffset(), packet.getLength(), StandardCharsets.UTF_8);
                System.out.println(message);
            }
        } catch (Exception e) {
            if (running && !socket.isClosed()) {
                e.printStackTrace();
            }
        }
    }

    private void listenMulticast(MulticastSocket socket) {
        try {
            while (true) {
                byte[] buffer = new byte[BUFFER_SIZE];
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                socket.receive(packet);
                String message = new String(packet.getData(), packet.getOffset(), packet.getLength(), StandardCharsets.UTF_8);
                
                if (message.startsWith("MCAST:")){
                    int separatorIndex = message.indexOf(':', 6);
                    if (separatorIndex == -1) {
                        continue;
                    }
                    
                    String sender = message.substring(6, separatorIndex);
                    String actualMessage = message.substring(separatorIndex + 1);

                    if (!sender.equals(localUsername)) {
                        System.out.println(sender + ": " + actualMessage);
                    }
                } else {
                    if (running && !socket.isClosed()) {
                        System.out.println(message);
                    }
                }
            }
        } catch (Exception e) {
            if (!socket.isClosed()) {
                e.printStackTrace();
            }
        }
    }

    private String readMultilineMessage(Scanner scanner){
        StringBuilder builder = new StringBuilder();
        while(true){
            String line = scanner.nextLine();
            if("END".equals(line)){
                break;
            }
            builder.append("\n").append(line);
        }
        return builder.toString();
    }

    private void sendUdpMessage(String username,String message, DatagramSocket socket) throws Exception {
        String payload = "MSG:" + username + ":"+ message;
        byte[] buffer = payload.getBytes(StandardCharsets.UTF_8);
        DatagramPacket packet = new DatagramPacket(buffer, buffer.length, InetAddress.getByName(SERVER_HOST), SERVER_PORT);
        socket.send(packet);
    }

    private void sendMulticastMessage(String message, MulticastSocket socket, InetAddress group) throws Exception {
        byte[] buffer = message.getBytes(StandardCharsets.UTF_8);
        DatagramPacket packet = new DatagramPacket(buffer, buffer.length, group, MULTICAST_PORT);
        socket.send(packet);
    }

    private void registerUdp(String username, DatagramSocket socket) throws Exception {
        String registrationMessage = "REGISTER:" + username;
        byte[] buffer = registrationMessage.getBytes(StandardCharsets.UTF_8);
        DatagramPacket packet = new DatagramPacket(buffer, buffer.length, InetAddress.getByName(SERVER_HOST), SERVER_PORT);
        socket.send(packet);
    }
}
