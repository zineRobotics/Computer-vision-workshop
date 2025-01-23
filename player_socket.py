import socket
import base64
import pygame
import threading
import numpy as np
import colorsys
import cv2
import json
import components
from player_logic import identify_shapes_and_colors

# Constants
BUFF_SIZE = 65536
# host_ip = '192.168.0.176'  # 192.168.0.176'
host_ip = '192.168.56.1'
port = 6060
WIDTH, HEIGHT = 1000, 600
SHAPES_LIST_WIDTH = 300
VIDEO_WIDTH = WIDTH - SHAPES_LIST_WIDTH
SHAPES_LIST_HEIGHT = HEIGHT
SHAPE_OFFSET_Y = 350

# Initialize pygame
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Zine CV - Client")
font = pygame.font.Font(None, 28)
last_processed_frame = None
# bg = pygame.image.load("score.jpg")
# bg = pygame.transform.scale(bg, (WIDTH, HEIGHT))
# Client state
client_socket = None
shapes_list = []
stage1_response=[]
running = True
frame_processed = False
team_name = ""
receive_score=0
receive_stage=1
recieve_tries=5

BASIC_COLORS = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "black": (0, 0, 0),
      "invalid": (255, 255, 255),
    "white": (255, 255, 255)
}

def get_simplified_color_name(hsv_color):
    """Map HSV color to red, green, blue, or invalid."""
    h, s, v = hsv_color

    if s < 0.2 or v < 0.2: #low saturation or value, invalid
        return "invalid"
    elif 0 <= h <= 20 or 160 <= h <= 180:  # Red (wraps around)
        return "red"
    elif 40 <= h <= 80:  # Green
        return "green"
    elif 100 <= h <= 140:  # Blue
        return "blue"
    else:
        return "invalid"
    
def hsv_to_rgb(hsv_color):
    """Convert HSV color to RGB."""
    h, s, v = hsv_color
    h = h/180.0
    s = s/255
    v = v/255
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))

def display_score_and_stage():
    global receive_score, receive_stage ,recieve_tries

    if receive_score is not None and receive_stage is not None:
        # Circular background for score
        pygame.draw.circle(screen, (0, 0, 0), (500, 50), 50)  # Blue circle at (400, 50) with radius 40
        score_text = font.render(f"Score: {receive_score}", True, components.WHITE)
        screen.blit(score_text, (500 - score_text.get_width() // 2, 50 - score_text.get_height() // 2))  # Center text

        # Circular background for stage
        pygame.draw.circle(screen, (0, 0, 0), (500, 150), 50)  # Red circle at (400, 150) with radius 40
        stage_text = font.render(f"Stage: {receive_stage}", True, components.WHITE)
        screen.blit(stage_text, (500 - stage_text.get_width() // 2, 150 - stage_text.get_height() // 2))  # Center text
        pygame.draw.circle(screen, (0, 0, 0), (500, 250), 50)  # Red circle at (400, 150) with radius 40
        stage_text = font.render(f"Tries: {recieve_tries}", True, components.WHITE)
        screen.blit(stage_text, (500 - stage_text.get_width() // 2, 250 - stage_text.get_height() // 2))  # Center text
    pygame.display.update()

def receive_message():
    global client_socket, frame_processed, last_processed_frame
    buffer = ""
    init_data = json.dumps({"type": "init", "team_name": team_name})
    client_socket.send(init_data.encode('utf-8'))
    global receive_stage,receive_score,recieve_tries

    while running:
        try:
            msg = client_socket.recv(BUFF_SIZE)
            if msg:
                buffer += msg.decode('utf-8')
                json_data, idx = json.JSONDecoder().raw_decode(buffer)
                # json_data = json.loads(msg.decode('utf-8'))
                # print(f"[INFO] Received data: {json_data['type']} ")
                # if json_data["type"] == "result":
                #     print(f"[INFO] Received results: {json_data['score']}")
                try:
                    # print(msg)
                    # json_data = json.loads(msg.decode('utf-8'))
                    # print("[INFO] Received data: ", json_data)
                    if json_data['type'] == 'video_frame':
                        receive_video(json_data['frame'])
                    elif json_data['type'] == 'result':
                       print(f"[INFO] Received results: {json_data['score']}")
                       
                       receive_score=json_data['score']
                       receive_stage=json_data['stage']
                       recieve_tries=json_data['tries']
                       print(f"json data:${receive_score}")
                    elif json_data['type'] == 'init':
                       receive_score=json_data['score']
                    #    receive_stage=json_data['stage']
                       recieve_tries=json_data['tries']
                except json.JSONDecodeError:
                    print(f"[ERROR] Failed to decode JSON data")
                buffer = buffer[idx:]
            else:
                print("[INFO] Connection closed by server")
                break
         
        except socket.error as e:
            print(f"[ERROR] Error receiving data from {e}")
        except Exception as e:
            print(f"[ERROR] Error: {e}")
            break
def process_and_draw(frame):
    nodes_shortest = shortest_path(frame)
    directions_creation(frame, nodes_shortest)

def receive_video(message):
    """Receive and display video stream."""
    global frame_processed, last_processed_frame,shapes_list
    frame_data = base64.b64decode(message)
    nparr = np.frombuffer(frame_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is not None:
        if frame_processed:
            shapes_list.clear()
            frame,result = identify_shapes_and_colors(frame)
            shapes_list = result
            last_processed_frame = frame.copy()

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = np.rot90(frame)
        frame_surface = pygame.surfarray.make_surface(frame)
        screen.blit(frame_surface, (0, 0))

        if last_processed_frame is not None:
            processed_frame_rgb = cv2.cvtColor(last_processed_frame, cv2.COLOR_BGR2RGB)
            processed_frame_rgb = np.rot90(processed_frame_rgb)
            # processed_frame_rgb = cv2.rotate(processed_frame_rgb, cv2.ROTATE_180)
            processed_frame_surface = pygame.surfarray.make_surface(processed_frame_rgb)

            processed_frame_x = VIDEO_WIDTH - processed_frame_surface.get_width() // 2
            screen.blit(processed_frame_surface, (processed_frame_x+130, 0))
            # print("\n\nshortest path\n:",shortest_path(last_processed_frame))
            # threading.Thread(target=process_and_draw,args=(last_processed_frame,), daemon=True).start()
            # nodes_shortest=shortest_path(last_processed_frame)
            # directions_creation(last_processed_frame, nodes_shortest)
            # print("Thread execution completed, proceeding further...")

        if frame_processed:
            draw_shape_list()
            frame_processed = False

        # pygame.display.update()

  
def draw_shape_list():
    """Draw the list of identified shapes at the bottom of the screen."""
    list_height = HEIGHT // 2 - 100  # Define the height of the shape list area
    list_y = HEIGHT // 2   # Position the list at the bottom of the screen
    pygame.draw.rect(screen, (0, 0, 0), (0, HEIGHT//2, WIDTH, HEIGHT//2-100))  

    y_offset = list_y + SHAPE_OFFSET_Y  # Start drawing text inside the bottom area
    column_width = SHAPES_LIST_WIDTH // 2 +30  # Width of each column
    column_x = WIDTH // 2 - column_width  # Start drawing from the center
    
    max_shapes_per_column = 6  # Number of shapes per column
    column_width = 150  # Width of each column
    start_x = 20  # Starting X position for first column
    start_y = list_y + 20
    for i, (shape, color_name) in enumerate(shapes_list):
        shape_text = font.render(f"{shape} - {color_name}", True, components.WHITE)

        # Calculate the current column index
        column_index = i // max_shapes_per_column  
        text_x = start_x + (column_index * column_width)  # Adjust column position
        text_y = start_y + (i % max_shapes_per_column) * 30  # Space each row by 30 pixels

        # Stop printing if we exceed the available width
        if text_x + column_width > WIDTH:
            break  # Prevent overflow beyond screen width

        screen.blit(shape_text, (text_x, text_y)) # Space between each entry

def send_shapes_to_server(team_name):
    """Send the current shapes list to the server."""
    global shapes_list, client_socket
    try:
        if recieve_tries == 0:
            show_message("Ran out of tries", (0, 255, 0)) 
            return

        shapes_data = json.dumps({
            "type": "answer",
            "team_name": team_name,
            "shapes": shapes_list})  # Convert shapes list to JSON format
        client_socket.send(shapes_data.encode('utf-8'))
        show_message("Shapes sent successfully!", (0, 255, 0))  # Green for success
        # print(shapes_data)
    except Exception as e:
        show_message(f"Error sending shapes: {e}", (255, 0, 0)) 


def show_message(message, color):
    """Display a temporary message on the Pygame window."""
    font = pygame.font.Font(None, 48)
    text_surface = font.render(message, True, color)
    text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(150) 
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))
    screen.blit(text_surface, text_rect)
    pygame.display.flip()
    pygame.time.delay(2000)
    screen.fill((0, 0, 0))
    pygame.display.update()


def get_team_name():
    global team_name
    """Display a Pygame window to input the team name and return it."""
    input_active = True

    input_box = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 20, 300, 40)
    color_inactive = pygame.Color('lightskyblue3')
    color_active = pygame.Color('dodgerblue2')
    color = color_inactive
    active = False
    watermark = pygame.image.load("score.jpg")  # Load the watermark image
    watermark = pygame.transform.scale(watermark, (WIDTH, HEIGHT))  # Resize to fit the screen
    watermark.set_alpha(0)

    screen.fill((0, 0, 0))  # Clear screen
    font = pygame.font.Font(None, 36)
    prompt_text = font.render("Enter your team name:", True, (255, 255, 255))
    screen.blit(prompt_text, (WIDTH//2 - prompt_text.get_width()//2, HEIGHT//2 - 60))

    while input_active:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                if input_box.collidepoint(event.pos):
                    active = not active
                else:
                    active = False
                color = color_active if active else color_inactive

            if event.type == pygame.KEYDOWN:
                if active:
                    if event.key == pygame.K_RETURN:
                        input_active = False  # Exit input loop
                    elif event.key == pygame.K_BACKSPACE:
                        team_name = team_name[:-1]
                    else:
                        team_name += event.unicode

        screen.fill((0, 0, 0))  # Clear screen again for updates
        screen.blit(prompt_text, (WIDTH//2 - prompt_text.get_width()//2, HEIGHT//2 - 60))
        screen.blit(watermark, (0, 0)) 
        pygame.draw.rect(screen, color, input_box, 2)
        text_surface = font.render(team_name, True, (255, 255, 255))
        screen.blit(text_surface, (input_box.x + 10, input_box.y + 5))

        pygame.display.flip()
        screen.fill((0, 0, 0))
        screen.blit(watermark, (0, 0)) 

    # pygame.quit()  # Close Pygame window after input
    return team_name


def start_client():
    """Connect to the server and handle events."""
    global team_name
    
    global client_socket, running
    # screen.blit(bg, (0, 0))
    team_name = get_team_name()
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_thread = threading.Thread(target=receive_message, daemon=True)

    try:
        client_socket.connect((host_ip, port))
        if not client_socket:
            print("[ERROR] Failed to connect to server")
            return
        
        # client_socket.sendto("REQUEST_STREAM".encode('utf-8'), (host_ip, port))
        print("[INFO] Connected to server")
        sock_thread.start()

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos
                    if 50 <= x <= 250 and HEIGHT - 100 <= y <= HEIGHT - 50:
                        process_frame()
                    elif 400 <= x <= 600 and HEIGHT - 100 <= y <= HEIGHT - 50:
                        running = False
                    elif 700 <= x <= 900 and HEIGHT - 100 <= y <= HEIGHT - 50:  # Send Shapes button
                        send_shapes_to_server(team_name)

            # Draw buttons
            pygame.draw.rect(screen, (100, 255, 100), (50, HEIGHT - 100, 200, 50))
            pygame.draw.rect(screen, (180, 10, 10), (400, HEIGHT - 100, 200, 50))
            pygame.draw.rect(screen, (100, 100, 255), (700, HEIGHT - 100, 200, 50))  # Blue button
            # pygame.draw.rect(screen, (100, 100, 255), (400, 200, 230, 50))  # Lighter blue
            # pygame.draw.rect(screen, (50, 50, 205), (400, 100, 230, 50))    # Medium blue
            # pygame.draw.rect(screen, (0, 0, 155), (400, 0, 230, 50))

            process_text = font.render("Process Frame", True, (255, 255, 255))
            disconnect_text = font.render("Disconnect", True, (255, 255, 255))
            send_shapes_text = font.render("Send Shapes", True, (255, 255, 255))

            screen.blit(process_text, (50 + 100 - process_text.get_width() // 2, HEIGHT - 90))
            screen.blit(disconnect_text, (400 + 100 - disconnect_text.get_width() // 2, HEIGHT - 90))
            screen.blit(send_shapes_text, (700 + 100 - send_shapes_text.get_width() // 2, HEIGHT - 90))
            
            display_score_and_stage()

            pygame.display.update()

    except Exception as e:
        print(f"[ERROR] Error: {e}")
    finally:
        if sock_thread.is_alive():
            sock_thread.join()

        if client_socket:
            client_socket.close()
        pygame.quit()
        print("[INFO] Disconnected")

def process_frame():
    """Set the flag to process the frame."""
    global frame_processed
    frame_processed = True
    print("[INFO] Processing frame...")


'''finding teh shortest path'''
def totalCost(mask, curr, n, cost, memo, parent):
    if mask == (1 << n) - 1:
        return cost[curr][start_node]
    if memo[curr][mask] != -1:
        return memo[curr][mask]
    ans = float('inf')
    next_city = -1
    for i in range(n):
        if (mask & (1 << i)) == 0:  
            temp_cost = cost[curr][i] + totalCost(mask | (1 << i), i, n, cost, memo, parent)
            if temp_cost < ans:
                ans = temp_cost
                next_city = i
    memo[curr][mask] = ans
    parent[curr][mask] = next_city
    return ans


def tsp(cost, start):
    global start_node
    start_node = start  

    n = len(cost)
    memo = [[-1] * (1 << n) for _ in range(n)]
    parent = [[-1] * (1 << n) for _ in range(n)]
    min_cost = totalCost(1 << start_node, start_node, n, cost, memo, parent)
    path = []
    mask = 1 << start_node
    curr = start_node
    while curr != -1:
        path.append(curr)
        curr = parent[curr][mask]
        if curr != -1:
            mask |= (1 << curr)
    path.append(start_node)
    return min_cost, path

def cost_matrix(result):
    
    n = len(result)
    return [[((result[j]['center_x'] - result[i]['center_x']) ** 2 +
              (result[j]['center_y'] - result[i]['center_y']) ** 2)
             for j in range(n)] for i in range(n)]
def decode_node(tour, result):
    
    return [(result[i]['center_x'], result[i]['center_y']) for i in tour] + \
           [(result[tour[0]]['center_x'], result[tour[0]]['center_y'])]


def find_starting_node(result_list, start_shape, start_color):
    """Find the index of the starting node based on shape and color."""
    for i, item in enumerate(result_list):
        if item['shape'] == start_shape and item['color'] == start_color:
            return i
    raise ValueError(f"No object found with shape '{start_shape}' and color '{start_color}'.")

def arrange_by_coordinates(result_list, node_cord):

    arranged_list = []
    
    for x, y in node_cord:
        for item in result_list:
            if item['center_x'] == x and item['center_y'] == y:
                arranged_list.append(item)
                break
    # list=send(arranged_list)                
                
    return list
def directions_creation(image, nodes):
                    
    for i in range(len(nodes) - 1):
        cv2.line(image, nodes[i], nodes[i + 1], (128, 0, 128), 2)
        cv2.imshow('Path', image)
        cv2.waitKey(500)
    cv2.waitKey(0)
def shortest_path(image):
    print("inside the function")
    _,result_list=identify_shapes_and_colors(image)
    cost = cost_matrix(result_list)
    # start_node = find_starting_node(result_list, "rectangle", "red")#randomly giving the value of shape and color
    start_node=0
    print("\n\n start_node",start_node)
    min_cost,best_tour = tsp(cost, start_node)
    node_coords = decode_node(best_tour, result_list)
    print("\n\n node_coords",node_coords)
    return node_coords
    # return arrange_by_coordinates(result_list, node_coords)
if __name__ == "__main__":
    start_client()