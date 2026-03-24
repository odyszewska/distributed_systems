package zad1;

import java.io.PrintWriter;
import java.net.InetAddress;

public class ClientInfo {
    private final String username;
    private final PrintWriter writer;
    private InetAddress udpAddress;
    private int udpPort = -1;

    public ClientInfo(String username, PrintWriter writer) {
        this.username = username;
        this.writer = writer;
    }

    public String getUsername() {
        return username;
    }
    public PrintWriter getWriter() {
        return writer;
    }
    public InetAddress getUdpAddress() {
        return udpAddress;
    }
    public int getUdpPort() {
        return udpPort;
    }

    public void setUdpEndpoint(InetAddress udpAddress, int udpPort) {
        this.udpAddress = udpAddress;
        this.udpPort = udpPort;
    }

    public boolean hasUdpEndpoint() {
        return udpAddress != null && udpPort > 0;
    }

    public synchronized void sendTcpMessage(String message) {
        writer.println(message);
    }
}