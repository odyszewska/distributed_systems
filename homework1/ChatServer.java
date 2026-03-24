package zad1;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;


public class ChatServer {
    private int PORT = 12345;
    private int BUFFER_SIZE = 1024;

    private Map<String, ClientInfo> clients = new ConcurrentHashMap<>();
    private ExecutorService executor = Executors.newCachedThreadPool();

    public static void main(String[] args) {
        new ChatServer().start();
    }

    public void start() {
        executor.execute(this::runUdpServer);

        try(ServerSocket serverSocket = new ServerSocket(PORT)) {
            System.out.println("Chat server started on port: " + PORT);
            while (true) {
                Socket clientSocket = serverSocket.accept();
                executor.execute(() -> handleTcpClient(clientSocket));
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private void handleTcpClient(Socket clientSocket) {
        String username = null;
        boolean validClient = false;
        ClientInfo clientInfo = null;
        
        try (Socket socket = clientSocket;
             BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
             PrintWriter writer = new PrintWriter(socket.getOutputStream(), true, StandardCharsets.UTF_8)) {
            
            username = reader.readLine();
            if (username != null){
                username = username.trim();
            }
            if (username == null || username.isEmpty()){
                writer.println("Username cannot be empty.");
                return;
            }

            clientInfo = new ClientInfo(username, writer);
            ClientInfo existingClient = clients.putIfAbsent(username, clientInfo);

            if (existingClient != null) {
                writer.println("Username already taken. Please choose another one.");
                return;
            }

            validClient = true;
            writer.println("OK");

            System.out.println("Client connected: " + username + " (" + socket.getInetAddress() + ":" + socket.getPort() + ")");
            broadcastTcpMessage("Server: " + username + " has joined the chat.", clientInfo);

            String message;
            while ((message = reader.readLine()) != null) {
                String fullMessage = username + ": " + message;
                System.out.println(fullMessage);
                broadcastTcpMessage(fullMessage, clientInfo);
            }

        } catch (IOException e) {
            System.out.println("Client connection error: " + e.getMessage());
        } finally {
            if (validClient && username != null) {
                System.out.println("Client disconnected: " + username);
                clients.remove(username);
                broadcastTcpMessage("Server: " + username + " has left the chat.", null);
            }
        }
    }

    private void broadcastTcpMessage(String message, ClientInfo exclude) {
        for (ClientInfo client : clients.values()) {
            if (client != exclude) {
                client.sendTcpMessage(message);
            }
        }
    }

    private void runUdpServer(){
        try(DatagramSocket udpSocket = new DatagramSocket(PORT)) {
            System.out.println("UDP server started on port: " + PORT);
            while (true) {
                byte[] buffer = new byte[BUFFER_SIZE];
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                udpSocket.receive(packet);
                
                String message = new String(packet.getData(), packet.getOffset(), packet.getLength(), StandardCharsets.UTF_8);
                
                if (message.startsWith("REGISTER:")) {
                    String username = message.substring("REGISTER:".length()).trim();
                    ClientInfo clientInfo = findClientByUsername(username);
                    if (clientInfo != null) {
                        clientInfo.setUdpEndpoint(packet.getAddress(), packet.getPort());
                        System.out.println("Registered UDP endpoint for " + username + "(" + packet.getAddress() + ":" + packet.getPort() + ")");
                    } else {
                        System.out.println("Received registration from unknown client: " + username);
                    }
                    continue;
                }

                if (message.startsWith("MSG:")) {
                    int separatorIndex = message.indexOf(':', 4);
                    if (separatorIndex == -1) {
                        System.out.println("Invalid message format: " + message);
                        continue;
                    }
                    String username = message.substring(4, separatorIndex);
                    String actualMessage = message.substring(separatorIndex + 1);
                    ClientInfo sender = findClientByUsername(username);

                    if (sender == null) {
                        System.out.println("Received message from unknown client: " + username);
                        continue;
                    }

                    if (!sender.hasUdpEndpoint()) {
                        System.out.println("Received UDP message from client without registered endpoint: " + username);
                        continue;
                    }

                    if(!sender.getUdpAddress().equals(packet.getAddress()) || sender.getUdpPort() != packet.getPort()) {
                        System.out.println("Received UDP message from unregistered endpoint for client: " + username);
                        continue;
                    }
                    String fullMessage = sender.getUsername() + ": " + actualMessage;
                    System.out.println(fullMessage);
                    broadcastUdpMessage(fullMessage, udpSocket, sender);
                    continue;
                }
                System.out.println("Received unknown UDP message: " + message);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private ClientInfo findClientByUsername(String username) {
        return clients.get(username);
    }

    private void broadcastUdpMessage(String message, DatagramSocket socket, ClientInfo exclude) throws IOException {
        byte[] buffer = message.getBytes(StandardCharsets.UTF_8);
        for (ClientInfo client : clients.values()) {
            if (client != exclude && client.hasUdpEndpoint()) {
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length, client.getUdpAddress(), client.getUdpPort());
                socket.send(packet);
            }
        }
    }
}