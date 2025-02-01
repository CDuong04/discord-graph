### **📌 Discord Graph Bot**  
A Discord bot that tracks user mentions in a designated channel and generates graph visualizations using **NetworkX, PyVis, and Matplotlib**. The bot also supports **AWS S3** for hosting interactive graphs.

---

## **⚡ Features**
- Tracks mentions and creates an **interactive graph** of connections.
- Generates **static** graph images using **Matplotlib**.
- Generates **interactive** graph HTML files using **PyVis**.
- Stores data in **MongoDB** for persistence.
- Supports **AWS S3** for hosting interactive graphs.
- Allows administrators to **set tracking channels** and **clear graphs**.
- Users can add, delete, and view connections.

---

## **🚀 Setup Instructions**

### **1. Clone the Repository**
```bash
git clone https://github.com/CDuong04/discord-graph.git
cd discord-graph
```

### **2. Install Dependencies**
Make sure you have Python installed (`>=3.8`), then install required dependencies:
```bash
pip install -r requirements.txt
```

### **3. Configure Environment Variables**
Create a `.env` file in the project root:
```
DISCORD_TOKEN=your_discord_bot_token
MONGODB_URI=your_mongodb_connection_uri
S3_BUCKET=your_aws_s3_bucket_name
S3_REGION=your_aws_region
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
```
Make sure your **AWS credentials** are set up using environment variables or `~/.aws/credentials`.

### **4. Run the Bot Locally**
```bash
python app.py
```

---

## **📖 Commands**

### **Basic Commands**
| Command            | Description                                        |
|--------------------|----------------------------------------------------|
| `-hello`          | Bot responds with "Hello!"                         |
| `-setchannel`     | Set the current channel for tracking mentions. **(Admin only)** |
| `-graph`          | Generate and send the **static** graph image.      |
| `-link`           | Generate and send a **hosted interactive graph**.  |
| `-connect @User1 @User2` | Connect mentioned users in the graph. |
| `-delete @User1 @User2` | Remove the connection between two users. |
| `-cleargraph`     | Clear the stored graph data. **(Admin only)** |

---

## **🚀 Deploying to Railway.app**
1. **Push your code to GitHub**.
2. **Create a new Railway project** and connect your GitHub repo.
3. **Set environment variables** (`DISCORD_TOKEN`, `MONGODB_URI`, etc.).
4. **Deploy** and check the logs to ensure the bot is running.

---

## **🛠 Technologies Used**
- **Python** (Discord.py, Asyncio)
- **MongoDB** (Data storage)
- **Matplotlib & NetworkX** (Static graphs)
- **PyVis** (Interactive graphs)
- **AWS S3** (Hosting interactive graphs)
- **Railway.app** (Cloud hosting)

---

## **📜 License**
This project is licensed under the **MIT License**.

---

## **📞 Contact & Support**
If you need help, feel free to open an issue in the [GitHub repository](https://github.com/CDuong04/discord-graph) or reach out to **@CDuong04** on GitHub.
