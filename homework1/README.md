# Chat Application

A simple Java chat application based on sockets.

The project implements a multi-client chat server and client with:
- **TCP** communication for standard chat messages
- **UDP** communication for multimedia-style messages
- **Multicast** communication as an alternative to UDP broadcast
- **multi-threaded server** handling multiple clients at the same time

## Features

- many clients can connect to the server at the same time
- every TCP client connection is handled in a separate task/thread
- messages sent over TCP are forwarded to all other connected clients
- UDP channel for sending additional messages with command `U`
- multicast channel for sending messages directly to the whole group with command `M`
- unique usernames for clients
- join/leave notifications

## Project structure

- `ChatServer.java` – server application
- `ChatClient.java` – client application
- `ClientInfo.java` – stores client data such as username, TCP writer, UDP address and UDP port :contentReference

## Commands

After starting the client, the following commands are available:

- type any normal text message → send via TCP
- type `U` → send a message via UDP
- type `M` → send a message via multicast
- type `exit` → close the client

For UDP and multicast messages, the client supports multiline input.  
Finish the message by typing 
`END`

## Compilation

Compile the project from the parent directory:

```bash
javac zad1/*.java
```
## How to run

Start the server first:
```bash
java zad1.ChatServer
```
Then start clients in separate terminals:
```bash
java zad1.ChatClient
```
Run at least two clients to test chat communication.

## Example usage

### 1. Start server
```bash
java zad1.ChatServer
```
### 2. Start first client
```bash
java zad1.ChatClient
```
Example:
```bash
Enter your username: Alice
```
### 3. Start second client
```bash
java zad1.ChatClient
```
Example:
```bash
Enter your username: Bob
```
### 4. Send normal TCP message

Client input:
```bash
Hello everyone
```
Other clients receive:
```bash
Alice: Hello everyone
```
### 5. Send UDP message

Client input:
```bash
U
```
Then enter multiline message, for example:
```bash
 /\_/\
( o.o )
 > ^ <
END
```
### 6. Send multicast message

Client input:
```bash
M
```
Then enter multiline message and finish with:
```bash
END
```