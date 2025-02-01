import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import networkx as nx
import io
from pymongo import MongoClient
from itertools import combinations  # for iterating through all pairs
import asyncio  # for wait_for timeout handling

# For static image generation using Matplotlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# For interactive graph generation (PyVis)
from pyvis.network import Network

# For AWS S3 uploading
import boto3
from botocore.exceptions import NoCredentialsError

# Load environment variables from the .env file
load_dotenv()

# Get the bot token, MongoDB URI, AWS S3 info, etc. from the environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI')  # e.g., "mongodb+srv://<user>:<password>@cluster0.mongodb.net/<dbname>?retryWrites=true&w=majority"

# AWS S3 settings
S3_BUCKET = os.getenv('S3_BUCKET')        # Your bucket name
S3_REGION = os.getenv('S3_REGION')          # e.g., "us-west-2" (optional if using default region)
# AWS credentials will be picked up from environment variables or AWS configuration

# Optional: If you have a logging channel, set its ID here.
LOGGING_CHANNEL_ID = int(os.getenv('LOGGING_CHANNEL_ID', '0'))

# Connect to MongoDB
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["discord_bot_db"]  # You can name the database as you like.
configs_collection = db["configs"]
graphs_collection = db["graphs"]

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True

bot = commands.Bot(command_prefix="-", intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


@bot.command()
async def hello(ctx):
    "Hi!"
    await ctx.send("Hello!")


# -----------------------------
# Setup command: Specify channel for tracking
# Only an administrator can run this command.
# -----------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    """Set the current channel as the designated channel for tracking pings/graph data."""
    guild = ctx.guild
    channel = ctx.channel

    if guild is None:
        await ctx.send("This command must be run within a server.")
        return

    configs_collection.update_one(
        {"guild_id": str(guild.id)},
        {"$set": {"channel_id": str(channel.id)}},
        upsert=True
    )

    await ctx.send(f"This channel ({channel.mention}) has been set as the designated channel for tracking pings and graph data.")


# -----------------------------
# Helper function to generate and send the static graph image using Matplotlib.
# -----------------------------
async def send_graph_image(ctx, guild, config):
    # Retrieve graph data from MongoDB.
    graph_data = graphs_collection.find_one({
        "guild_id": str(guild.id),
        "channel_id": config.get("channel_id")
    })
    if graph_data is None or ("nodes" not in graph_data or len(graph_data["nodes"]) == 0):
        await ctx.send("No graph data available for this server yet!")
        return

    # Reconstruct the NetworkX graph.
    G = nx.Graph()
    G.add_nodes_from(graph_data["nodes"])  # these are user IDs as strings
    G.add_edges_from(graph_data["edges"])

    # Create a copy for display; remove nodes that do not map to a User in the guild.
    display_G = G.copy()
    for node in list(G.nodes()):
        member = guild.get_member(int(node))
        if member is None:
            display_G.remove_node(node)

    # Build a labels dictionary (using the member's display name).
    labels = {}
    for node in display_G.nodes():
        member = guild.get_member(int(node))
        if member is not None:
            labels[node] = member.display_name

    # Generate the static graph image using Matplotlib.
    plt.figure(figsize=(8, 6))
    pos = nx.spring_layout(display_G)
    nx.draw_networkx(display_G, pos, labels=labels, with_labels=True, node_size=500, font_size=8, node_color="skyblue")
    plt.title(f"Graph for {guild.name}")

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()

    file = discord.File(fp=buf, filename="graph.png")
    await ctx.send(file=file)


# -----------------------------
# Helper function to generate the interactive PyVis graph HTML file locally.
# -----------------------------
def generate_pyvis_html(guild, config):
    # Retrieve graph data from MongoDB.
    graph_data = graphs_collection.find_one({
        "guild_id": str(guild.id),
        "channel_id": config.get("channel_id")
    })
    if graph_data is None or ("nodes" not in graph_data or len(graph_data["nodes"]) == 0):
        return None

    # Reconstruct the NetworkX graph.
    G = nx.Graph()
    G.add_nodes_from(graph_data["nodes"])
    G.add_edges_from(graph_data["edges"])

    # Create a copy for display; remove nodes that do not map to a User.
    display_G = G.copy()
    for node in list(G.nodes()):
        member = guild.get_member(int(node))
        if member is None:
            display_G.remove_node(node)

    # Create the PyVis network with light mode settings.
    net = Network(height="100vh", width="100%", bgcolor="#FFFFFF", font_color="black")
    net.barnes_hut()

    # Set options to enlarge nodes and edges.
    net.set_options('''
    var options = {
      "nodes": {
        "scaling": {
          "min": 20,
          "max": 50
        },
        "font": {
          "size": 20,
          "face": "arial"
        }
      },
      "edges": {
        "width": 3,
        "color": {
          "inherit": true
        },
        "smooth": {
          "enabled": true,
          "type": "dynamic"
        }
      }
    }
    ''')

    # Add nodes with labels (using member display names when available).
    for node in display_G.nodes():
        member = guild.get_member(int(node))
        label = member.display_name if member is not None else node
        net.add_node(node, label=label)
    for edge in display_G.edges():
        net.add_edge(*edge)

    # Save to a temporary HTML file.
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    temp_file.close()
    net.write_html(temp_file.name)
    return temp_file.name




# -----------------------------
# Command to display the static graph image.
# -----------------------------
@bot.command()
async def graph(ctx):
    "Display existing friendship graph"
    guild = ctx.guild
    channel = ctx.channel
    if guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    config = configs_collection.find_one({"guild_id": str(guild.id)})
    if config is None:
        await ctx.send("The tracking channel has not been set up yet. Please run `-setchannel` in the channel you wish to use.")
        return

    if str(channel.id) != config.get("channel_id"):
        await ctx.send("This command can only be used in the designated tracking channel.")
        return

    await send_graph_image(ctx, guild, config)


# -----------------------------
# Command to connect users via pings.
# This command creates connections (edges) between all mentioned users.
# If the command author is explicitly pinged, they will be included;
# otherwise, only the mentioned users (excluding the author) will be connected.
# After adding the connections, an interactive graph link is generated and returned.
# -----------------------------
@bot.command()
async def connect(ctx):
    """Connect all mentioned users with each other.
    
    If the command author is explicitly pinged, they will be included;
    otherwise, only the mentioned users (excluding the author) will be connected.
    After connecting, an interactive graph link is generated and returned.
    """
    guild = ctx.guild
    channel = ctx.channel

    if guild is None:
        await ctx.send("This command must be run within a server.")
        return

    config = configs_collection.find_one({"guild_id": str(guild.id)})
    if config is None:
        await ctx.send("The tracking channel has not been set up yet. Please run `-setchannel` in the channel you wish to use.")
        return

    if str(channel.id) != config.get("channel_id"):
        await ctx.send("This command can only be used in the designated tracking channel.")
        return

    members_to_connect = ctx.message.mentions
    if len(members_to_connect) < 2:
        await ctx.send("Error: You must mention at least two users to create connections.")
        return

    # Retrieve the existing document from MongoDB (if any)
    doc = graphs_collection.find_one({"guild_id": str(guild.id), "channel_id": config.get("channel_id")})
    existing_edges = []
    if doc and "edges" in doc:
        existing_edges = doc["edges"]

    new_edges = []
    new_nodes = set()
    already_connected = []

    # Iterate over every pair of mentioned users.
    for member1, member2 in combinations(members_to_connect, 2):
        edge = sorted([str(member1.id), str(member2.id)])
        if edge in existing_edges:
            already_connected.append((member1, member2))
        else:
            new_edges.append(edge)
            new_nodes.add(str(member1.id))
            new_nodes.add(str(member2.id))

    # If no new connections are added:
    if not new_edges:
        await ctx.send("These users are already connected.")
    else:
        graphs_collection.update_one(
            {"guild_id": str(guild.id), "channel_id": config.get("channel_id")},
            {"$addToSet": {
                "nodes": {"$each": list(new_nodes)},
                "edges": {"$each": new_edges}
            }},
            upsert=True
        )
        await ctx.send("New connections added between the mentioned users.")

    # Generate interactive graph link:
    html_file = generate_pyvis_html(guild, config)
    if html_file is None:
        await ctx.send("No graph data available for this server!")
        return

    import time
    object_name = f"graph_{guild.id}_{int(time.time())}.html"
    url = upload_file_to_s3(html_file, S3_BUCKET, object_name)
    if url:
        await ctx.send(f"Here is your interactive graph: {url}")
    else:
        await ctx.send("Failed to upload the graph to S3.")

    try:
        os.remove(html_file)
    except Exception as e:
        print(f"Could not remove temporary file: {e}")


# -----------------------------
# Command to clear the stored graph.
# Only an administrator can run this command.
# -----------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def cleargraph(ctx):
    """Clear the stored graph data for this server in the designated channel, with confirmation."""
    guild = ctx.guild
    channel = ctx.channel
    if guild is None:
        await ctx.send("This command must be run within a server.")
        return

    config = configs_collection.find_one({"guild_id": str(guild.id)})
    if config is None:
        await ctx.send("The tracking channel has not been set up yet.")
        return

    if str(channel.id) != config.get("channel_id"):
        await ctx.send("This command can only be used in the designated tracking channel.")
        return

    await ctx.send("Are you sure you want to clear the graph data? Type `yes` to confirm. (This will timeout in 30 seconds)")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        confirmation = await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("Confirmation timed out. Graph data was not cleared.")
        return

    if confirmation.content.lower() != "yes":
        await ctx.send("Graph data clearing cancelled.")
        return

    result = graphs_collection.delete_one({"guild_id": str(guild.id), "channel_id": config.get("channel_id")})
    if result.deleted_count:
        await ctx.send("Graph data cleared.")
    else:
        await ctx.send("No graph data to clear.")


# -----------------------------
# Command to delete a connection.
# This command deletes the connection (edge) between exactly two pinged users.
# Usage: -delete @User1 @User2
# -----------------------------
@bot.command()
async def delete(ctx):
    """Delete the connection (edge) between exactly two pinged users.
    
    Usage: -delete @User1 @User2
    """
    guild = ctx.guild
    channel = ctx.channel

    if guild is None:
        await ctx.send("This command must be run within a server.")
        return

    config = configs_collection.find_one({"guild_id": str(guild.id)})
    if config is None:
        await ctx.send("The tracking channel has not been set up yet. Please run `-setchannel` in the channel you wish to use.")
        return

    if str(channel.id) != config.get("channel_id"):
        await ctx.send("This command can only be used in the designated tracking channel.")
        return

    members_to_delete = ctx.message.mentions
    if len(members_to_delete) != 2:
        await ctx.send("Error: You must mention exactly two users to delete a connection.")
        return

    member1, member2 = members_to_delete
    edge = sorted([str(member1.id), str(member2.id)])

    result = graphs_collection.update_one(
        {"guild_id": str(guild.id), "channel_id": config.get("channel_id")},
        {"$pull": {"edges": edge}}
    )

    if result.modified_count:
        await ctx.send(f"Connection between {member1.mention} and {member2.mention} has been deleted.")
    else:
        await ctx.send("No connection between the mentioned users was found.")

    # Generate an interactive graph link instead of a static image.
    html_file = generate_pyvis_html(guild, config)
    if html_file is None:
        await ctx.send("No graph data available for this server!")
        return

    import time
    object_name = f"graph_{guild.id}_{int(time.time())}.html"
    url = upload_file_to_s3(html_file, S3_BUCKET, object_name)
    if url:
        await ctx.send(f"Here is your updated interactive graph: {url}")
    else:
        await ctx.send("Failed to upload the graph to S3.")

    try:
        os.remove(html_file)
    except Exception as e:
        print(f"Could not remove temporary file: {e}")


# -----------------------------
# AWS S3 Helper: Upload a file and return its public URL.
# -----------------------------
def upload_file_to_s3(file_path, bucket, object_name):
    s3 = boto3.client("s3")
    try:
        s3.upload_file(
            file_path, 
            bucket, 
            object_name, 
            ExtraArgs={
                "ACL": "public-read",   # Since your bucket allows ACLs, this makes the object public.
                "ContentType": "text/html"
            }
        )
        url = f"https://{bucket}.s3.amazonaws.com/{object_name}"
        return url
    except FileNotFoundError:
        print("The file was not found.")
        return None
    except NoCredentialsError:
        print("Credentials not available.")
        return None


# -----------------------------
# Command to provide a link to the interactive PyVis graph.
# This command generates the interactive graph, uploads it to AWS S3,
# and sends a URL link.
# -----------------------------
@bot.command()
async def link(ctx):
    """Generate an interactive graph using PyVis, upload it to AWS S3, and return the public URL."""
    guild = ctx.guild
    channel = ctx.channel
    if guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    config = configs_collection.find_one({"guild_id": str(guild.id)})
    if config is None:
        await ctx.send("The tracking channel has not been set up yet. Please run `-setchannel` in the channel you wish to use.")
        return

    if str(channel.id) != config.get("channel_id"):
        await ctx.send("This command can only be used in the designated tracking channel.")
        return

    html_file = generate_pyvis_html(guild, config)
    if html_file is None:
        await ctx.send("No graph data available for this server yet!")
        return

    import time
    object_name = f"graph_{guild.id}_{int(time.time())}.html"
    url = upload_file_to_s3(html_file, S3_BUCKET, object_name)
    if url:
        await ctx.send(f"Here is your interactive graph: {url}")
    else:
        await ctx.send("Failed to upload the graph to S3.")

    try:
        os.remove(html_file)
    except Exception as e:
        print(f"Could not remove temporary file: {e}")


# -----------------------------
# on_message event handler (only processes commands now)
# -----------------------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)


# -----------------------------
# Error handling for missing permissions on admin commands.
# -----------------------------
@setchannel.error
@cleargraph.error
async def admin_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command. (Administrator permission required)")
    else:
        await ctx.send("An error occurred while processing the command.")


@bot.event
async def on_error(event, *args, **kwargs):
    import traceback
    error_message = traceback.format_exc()
    logging_channel = bot.get_channel(LOGGING_CHANNEL_ID)
    if logging_channel:
        await logging_channel.send(f"⚠️ **Error in {event}:**\n```python\n{error_message[:1900]}\n```")
    else:
        print(f"Logging channel not found! Error:\n{error_message}")


# Start the bot.
bot.run(TOKEN)
