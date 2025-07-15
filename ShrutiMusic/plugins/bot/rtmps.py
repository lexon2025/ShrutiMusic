import asyncio
import os
import subprocess
import logging
from typing import Dict, Optional
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from ShrutiMusic import app
from ShrutiMusic.utils.decorators import AdminRightsCheck

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global dictionary to store live stream sessions
live_sessions: Dict[int, Dict] = {}

class LiveStreamManager:
    def __init__(self):
        self.active_streams = {}
        self.ffmpeg_processes = {}
    
    def is_streaming(self, chat_id: int) -> bool:
        """Check if a chat is currently streaming"""
        return chat_id in self.active_streams
    
    def start_stream(self, chat_id: int, video_path: str, rtmp_url: str, stream_key: str) -> bool:
        """Start RTMPS stream for a video"""
        try:
            # Complete RTMPS URL
            full_rtmp_url = f"{rtmp_url}/{stream_key}"
            
            # FFmpeg command for streaming
            ffmpeg_cmd = [
                'ffmpeg',
                '-re',  # Read input at native frame rate
                '-i', video_path,  # Input video file
                '-c:v', 'libx264',  # Video codec
                '-preset', 'veryfast',  # Encoding speed
                '-maxrate', '3000k',  # Max bitrate
                '-bufsize', '6000k',  # Buffer size
                '-pix_fmt', 'yuv420p',  # Pixel format
                '-g', '50',  # GOP size
                '-c:a', 'aac',  # Audio codec
                '-b:a', '160k',  # Audio bitrate
                '-ac', '2',  # Audio channels
                '-ar', '44100',  # Audio sample rate
                '-f', 'flv',  # Output format
                full_rtmp_url  # RTMPS destination
            ]
            
            # Start FFmpeg process
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )
            
            self.ffmpeg_processes[chat_id] = process
            self.active_streams[chat_id] = {
                'video_path': video_path,
                'rtmp_url': rtmp_url,
                'stream_key': stream_key,
                'process': process
            }
            
            logger.info(f"Started live stream for chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting stream for chat {chat_id}: {str(e)}")
            return False
    
    def stop_stream(self, chat_id: int) -> bool:
        """Stop active stream"""
        try:
            if chat_id in self.ffmpeg_processes:
                process = self.ffmpeg_processes[chat_id]
                process.terminate()
                process.wait(timeout=10)
                
                del self.ffmpeg_processes[chat_id]
                del self.active_streams[chat_id]
                
                logger.info(f"Stopped live stream for chat {chat_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error stopping stream for chat {chat_id}: {str(e)}")
            return False
    
    def get_stream_status(self, chat_id: int) -> Optional[Dict]:
        """Get current stream status"""
        if chat_id in self.active_streams:
            process = self.ffmpeg_processes[chat_id]
            if process.poll() is None:  # Process is still running
                return self.active_streams[chat_id]
            else:
                # Process ended, clean up
                self.stop_stream(chat_id)
        return None

# Initialize stream manager
stream_manager = LiveStreamManager()

@app.on_message(filters.command("startlive"))
@AdminRightsCheck
async def start_live_command(client, message: Message):
    """Handle /startlive command"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Check if bot is in voice chat
    try:
        from ShrutiMusic.core.call import Shruti
        if chat_id not in Shruti.active_calls:
            await message.reply_text(
                "❌ <b>Bot isn't streaming on voice chat!</b>\n"
                "Please start a voice chat session first using <code>/play</code> command."
            )
            return
    except Exception as e:
        logger.warning(f"Could not check voice chat status: {e}")
    
    # Check if already streaming
    if stream_manager.is_streaming(chat_id):
        await message.reply_text(
            "❌ <b>A live stream is already active!</b>\n"
            "Please use <code>/stoplive</code> command to stop the current stream first."
        )
        return
    
    # Check if replying to a video
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply_text(
            "❌ <b>Please reply to a video message to use this command!</b>\n"
            "Usage: Reply to any video and type <code>/startlive</code>"
        )
        return
    
    # Initialize session data
    live_sessions[user_id] = {
        'chat_id': chat_id,
        'video_message': message.reply_to_message,
        'step': 'channel_input',
        'data': {}
    }
    
    # Ask for channel/group info
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_live_{user_id}")]
    ])
    
    await message.reply_text(
        "🎥 <b>Live Stream Setup</b>\n\n"
        "<b>Step 1/3:</b> Enter Channel/Group Information\n"
        "Please send the target channel or group <b>Chat ID</b> or <b>Username</b>:\n\n"
        "📝 <b>Examples:</b>\n"
        "• <code>@your_channel</code>\n"
        "• <code>-1001234567890</code>\n"
        "• <code>your_group_username</code>\n\n"
        "💡 <b>Note:</b> Bot must be admin in the target channel/group",
        reply_markup=keyboard
    )

@app.on_message(filters.text & filters.private)
async def handle_live_setup(client, message: Message):
    """Handle live stream setup inputs"""
    user_id = message.from_user.id
    
    if user_id not in live_sessions:
        return
    
    session = live_sessions[user_id]
    step = session['step']
    
    if step == 'channel_input':
        # Validate and store channel info
        channel_input = message.text.strip()
        session['data']['channel'] = channel_input
        session['step'] = 'server_url'
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_live_{user_id}")]
        ])
        
        await message.reply_text(
            "✅ <b>Channel/Group saved!</b>\n\n"
            "<b>Step 2/3:</b> Enter RTMPS Server URL\n"
            "Please send your <b>RTMPS Server URL</b>:\n\n"
            "📝 <b>Examples:</b>\n"
            "• <code>rtmps://live.example.com/live</code>\n"
            "• <code>rtmp://your-server.com/live</code>",
            reply_markup=keyboard
        )
    
    elif step == 'server_url':
        # Validate and store server URL
        server_url = message.text.strip()
        if not (server_url.startswith('rtmp://') or server_url.startswith('rtmps://')):
            await message.reply_text(
                "❌ <b>Invalid URL format!</b>\n"
                "URL must start with <code>rtmp://</code> or <code>rtmps://</code>"
            )
            return
        
        session['data']['server_url'] = server_url
        session['step'] = 'stream_key'
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_live_{user_id}")]
        ])
        
        await message.reply_text(
            "✅ <b>Server URL saved!</b>\n\n"
            "<b>Step 3/3:</b> Enter Stream Key\n"
            "Please send your <b>Stream Key</b>:\n\n"
            "📝 <b>Examples:</b>\n"
            "• <code>sk_live_1234567890abcdef</code>\n"
            "• <code>your_stream_key_here</code>",
            reply_markup=keyboard
        )
    
    elif step == 'stream_key':
        # Final step - start streaming
        stream_key = message.text.strip()
        session['data']['stream_key'] = stream_key
        
        # Start the live stream
        await start_live_stream(client, message, session)
        
        # Clean up session
        del live_sessions[user_id]

async def start_live_stream(client, message: Message, session: Dict):
    """Start the actual live stream"""
    try:
        video_message = session['video_message']
        chat_id = session['chat_id']
        channel = session['data']['channel']
        server_url = session['data']['server_url']
        stream_key = session['data']['stream_key']
        
        # Validate bot is still in voice chat
        try:
            from ShrutiMusic.core.call import Shruti
            if chat_id not in Shruti.active_calls:
                await message.reply_text(
                    "❌ <b>Bot is no longer in voice chat!</b>\n"
                    "Please rejoin voice chat and try again."
                )
                return
        except Exception as e:
            logger.warning(f"Could not verify voice chat status: {e}")
        
        # Send processing message
        status_msg = await message.reply_text(
            "🔄 <b>Processing...</b>\n"
            "Downloading video, please wait..."
        )
        
        # Download video
        video_path = await video_message.download(
            file_name=f"live_stream_{chat_id}_{video_message.message_id}.mp4"
        )
        
        # Update status
        await status_msg.edit_text(
            "🚀 <b>Starting Live Stream...</b>\n"
            "Establishing RTMPS connection..."
        )
        
        # Start streaming
        success = stream_manager.start_stream(chat_id, video_path, server_url, stream_key)
        
        if success:
            # Success message with controls
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⏹️ Stop Stream", callback_data=f"stop_stream_{chat_id}"),
                    InlineKeyboardButton("📊 Status", callback_data=f"stream_status_{chat_id}")
                ]
            ])
            
            await status_msg.edit_text(
                "✅ <b>Live Stream Started Successfully!</b>\n\n"
                f"📺 <b>Channel:</b> <code>{channel}</code>\n"
                f"🌐 <b>Server:</b> <code>{server_url}</code>\n"
                f"🔑 <b>Stream Key:</b> <code>{stream_key[:10]}...</code>\n"
                f"🎵 <b>Video:</b> {video_message.video.file_name or 'Unknown'}\n\n"
                "<b>Stream Controls:</b>",
                reply_markup=keyboard
            )
        else:
            await status_msg.edit_text(
                "❌ <b>Stream Start Failed!</b>\n"
                "Please check your server URL and stream key."
            )
            
            # Clean up downloaded file
            if os.path.exists(video_path):
                os.remove(video_path)
    
    except Exception as e:
        logger.error(f"Error in start_live_stream: {str(e)}")
        await message.reply_text(
            f"❌ <b>Error occurred:</b>\n<code>{str(e)}</code>"
        )

@app.on_callback_query(filters.regex(r"cancel_live_(\d+)"))
async def cancel_live_setup(client, callback_query):
    """Cancel live stream setup"""
    user_id = int(callback_query.data.split("_")[2])
    
    if user_id in live_sessions:
        del live_sessions[user_id]
    
    await callback_query.message.edit_text(
        "❌ <b>Live Stream Setup Cancelled</b>"
    )

@app.on_callback_query(filters.regex(r"stop_stream_(-?\d+)"))
async def stop_stream_callback(client, callback_query):
    """Stop live stream via callback"""
    chat_id = int(callback_query.data.split("_")[2])
    
    if stream_manager.stop_stream(chat_id):
        await callback_query.message.edit_text(
            "⏹️ <b>Live Stream Stopped Successfully!</b>"
        )
    else:
        await callback_query.answer("❌ No active stream found!", show_alert=True)

@app.on_callback_query(filters.regex(r"stream_status_(-?\d+)"))
async def stream_status_callback(client, callback_query):
    """Show stream status"""
    chat_id = int(callback_query.data.split("_")[2])
    
    status = stream_manager.get_stream_status(chat_id)
    if status:
        await callback_query.answer(
            f"🟢 Stream Active\n"
            f"Video: {os.path.basename(status['video_path'])}\n"
            f"Server: {status['rtmp_url']}", 
            show_alert=True
        )
    else:
        await callback_query.answer("❌ No active stream!", show_alert=True)

@app.on_message(filters.command("stoplive"))
@AdminRightsCheck
async def stop_live_command(client, message: Message):
    """Stop live stream command"""
    chat_id = message.chat.id
    
    if stream_manager.stop_stream(chat_id):
        await message.reply_text(
            "⏹️ <b>Live Stream Stopped Successfully!</b>"
        )
    else:
        await message.reply_text(
            "❌ <b>No active live stream found!</b>"
        )

@app.on_message(filters.command("livestatus"))
@AdminRightsCheck
async def live_status_command(client, message: Message):
    """Check live stream status"""
    chat_id = message.chat.id
    
    status = stream_manager.get_stream_status(chat_id)
    if status:
        await message.reply_text(
            "📊 <b>Live Stream Status</b>\n\n"
            f"🟢 <b>Status:</b> Active\n"
            f"🎵 <b>Video:</b> {os.path.basename(status['video_path'])}\n"
            f"🌐 <b>Server:</b> <code>{status['rtmp_url']}</code>\n"
            f"🔑 <b>Stream Key:</b> <code>{status['stream_key'][:10]}...</code>"
        )
    else:
        await message.reply_text(
            "📊 <b>Live Stream Status</b>\n\n"
            "🔴 <b>Status:</b> No active stream"
        )

# Cleanup function for app shutdown
@app.on_message(filters.command("vcstatus"))
@AdminRightsCheck
async def voice_chat_status(client, message: Message):
    """Check voice chat status"""
    chat_id = message.chat.id
    
    try:
        from ShrutiMusic.core.call import Shruti
        if chat_id in Shruti.active_calls:
            await message.reply_text(
                "🟢 <b>Voice Chat Status</b>\n\n"
                "✅ Bot is connected to voice chat\n"
                "🎵 Ready for live streaming"
            )
        else:
            await message.reply_text(
                "🔴 <b>Voice Chat Status</b>\n\n"
                "❌ Bot is not in voice chat\n"
                "💡 Use <code>/play</code> to join voice chat first"
            )
    except Exception as e:
        await message.reply_text(
            "⚠️ <b>Could not check voice chat status</b>\n"
            f"Error: <code>{str(e)}</code>"
        )
async def cleanup_streams():
    """Cleanup all active streams on shutdown"""
    for chat_id in list(stream_manager.active_streams.keys()):
        stream_manager.stop_stream(chat_id)
    logger.info("All live streams cleaned up")

# Register cleanup function
import atexit
atexit.register(lambda: asyncio.run(cleanup_streams()))

logger.info("Live Stream Plugin loaded successfully!")
