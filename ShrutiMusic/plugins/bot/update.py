# MIT License

# Copyright (c) 2025 NoxxOP

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import os
from ShrutiMusic import app

user_states = {}

def create_gitignore():
    """Create .gitignore to exclude unwanted files"""
    gitignore_content = """temp_bot.session
log.txt
*.session
*.log
__pycache__/
"""
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)

@app.on_message(filters.command("gitupdate") & filters.private)
async def git_update_force(client, message: Message):
    user_id = message.from_user.id
    user_states[user_id] = "waiting_token"

    await message.reply_text(  
        "🔐 Please send your <b>GitHub Personal Access Token (Classic)</b>:",  
        disable_web_page_preview=True  
    )

@app.on_message(filters.private & filters.text)
async def handle_responses(client, message: Message):
    user_id = message.from_user.id

    if user_id not in user_states:  
        return  
      
    if user_states[user_id] == "waiting_token":  
        token = message.text.strip()  
          
        if not token or len(token) < 20:  
            await message.reply_text("❌ Invalid token format. Please try again with <b>/gitupdate</b>")  
            del user_states[user_id]  
            return  
          
        user_states[user_id] = {"state": "waiting_repo", "token": token}  
        await message.reply_text(  
            "📦 Now send your <b>GitHub Repo URL</b> (e.g., https://github.com/username/repo):",  
            disable_web_page_preview=True  
        )  
          
    elif isinstance(user_states[user_id], dict) and user_states[user_id]["state"] == "waiting_repo":  
        repo_url = message.text.strip()  
        token = user_states[user_id]["token"]  
          
        try:  
            if "github.com/" not in repo_url:  
                raise ValueError("Invalid GitHub URL")  
            repo_slug = repo_url.split("github.com/")[1]  
            if repo_slug.endswith('.git'):  
                repo_slug = repo_slug[:-4]  
        except (IndexError, ValueError):  
            await message.reply_text("❌ Invalid repo URL. Please provide a valid GitHub repository URL.")  
            del user_states[user_id]  
            return  
          
        del user_states[user_id]  
          
        await message.reply_text(  
            "🔄 <b>Syncing your repo with upstream...</b> Please wait.",  
            disable_web_page_preview=True  
        )  
          
        try:  
            # Create .gitignore to exclude unwanted files
            create_gitignore()
            
            # Remove unwanted files before git operations
            cleanup_files = ["temp_bot.session", "log.txt"]
            for file in cleanup_files:
                if os.path.exists(file):
                    os.remove(file)
            
            commands = [  
                "rm -rf .git",  
                "git init",  
                f"git remote add origin https://{token}@github.com/{repo_slug}.git",  
                "git remote add upstream https://github.com/NoxxOP/ShrutiMusic.git",  
                "git config user.name 'Nand Yaduwanshi'",  
                "git config user.email 'badboy809075@gmail.com'",  
                "git fetch upstream",  
                "git checkout -b main",  
                "git reset --hard upstream/main",  
                "git add -A",  
                "git commit -m 'ᴛᴇʟᴇɢʀᴀᴍ @Sʜʀᴜᴛᴜʙᴏᴛs' --allow-empty",  
                "git push origin main --force"  
            ]  
              
            for cmd in commands:  
                try:  
                    process = await asyncio.create_subprocess_shell(  
                        cmd,  
                        stdout=asyncio.subprocess.PIPE,  
                        stderr=asyncio.subprocess.PIPE  
                    )  
                    stdout, stderr = await process.communicate()  
                      
                    if process.returncode != 0:  
                        error_msg = stderr.decode() if stderr else "Unknown error"  
                        await message.reply_text(  
                            f"❌ <b>Error during update:</b>\n<code>{error_msg}</code>",  
                            disable_web_page_preview=True  
                        )  
                        return  
                          
                except Exception as e:  
                    await message.reply_text(  
                        f"❌ <b>Command failed:</b> {cmd}\n<code>{str(e)}</code>",  
                        disable_web_page_preview=True  
                    )  
                    return  
              
            await message.reply_text(  
                "✅ <b>Your repo has been fully synced with the main repo.</b>\n\n"  
                "🔗 Now it's identical to: https://github.com/NoxxOP/ShrutiMusic",  
                disable_web_page_preview=True  
            )  
              
        except Exception as e:  
            await message.reply_text(  
                f"❌ <b>Unexpected error:</b>\n<code>{str(e)}</code>",  
                disable_web_page_preview=True  
            )
