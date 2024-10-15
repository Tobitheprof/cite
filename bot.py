import discord
import subprocess
import whisper
import os
from openai import OpenAI
from discord.ui import Button, View
import torch
from datetime import datetime
import markdown
import html
import html2text 
from weasyprint import HTML, CSS
import uuid 
from PIL import Image, ImageDraw, ImageFont
import re
from markdown2 import markdown as mdn

# Check if CUDA is available
if torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"
print(f"Using device: {device}")

# Set up the Discord bot and OpenAI API keys
TOKEN = "DISCORD_BOT_TOKEN"  # Replace with your actual bot token
api_key = "OPENAI_API_KEY"  # Replace with your actual OpenAI API key
client = OpenAI(api_key=api_key)
intents = discord.Intents.default()
intents.messages = True
bot = discord.Bot(intents=intents)

model = whisper.load_model("base", device=device)

# Function to generate and save PDF
def generate_pdf_from_markdown(md_content, filename="output.pdf"):
    # Convert markdown to HTML
    custom_css = CSS(string="""
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');
    
    @page {
        size: A4;
        margin: 1cm;
    }
    body {
        font-family: 'Poppins', sans-serif;  /* Use Poppins for body */
        font-size: 30px !important;
        line-height: 1.6;
        color: #333;
    }
    h1, h2, h3 {
        font-family: 'Poppins', sans-serif;  /* Use Poppins for headings */
        font-weight: 600;  /* Bold weight for headings */
        color: #333;
    }
    @page {
        @bottom-center {
            content: "Cite by Tobi TheRevolutionary";  /* Footer content */
            font-size: 10px;
            color: #555;  /* Footer text color */
            font-family: 'Poppins', sans-serif;
        }
    }
    """)
    html_content = markdown.markdown(md_content)

    # Convert the HTML to a PDF using WeasyPrint
    HTML(string=html_content).write_pdf(filename, stylesheets=[custom_css])
    print(f"PDF generated successfully: {filename}")

def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def get_uuid():
    return uuid.uuid4()

def markdown_to_plain_text(md):
    html_content = mdn(md)
    return html2text.html2text(html_content).strip()

# Convert Markdown to plain text
def markdown_to_plain_text(md):
    html_content = markdown.markdown(md)
    return html.unescape(html2text.html2text(html_content))

# Split long text into chunks within a token limit
def chunk_text(text, max_token_length):
    return [text[i:i + max_token_length] for i in range(0, len(text), max_token_length)]


# Help command
@bot.command(name="help", description="Get help with using the bot")
async def help_command(ctx):
    embed = discord.Embed(
        title="Help - Cite Discord Bot",
        description="Cite is the first comprehensive X Spaces tool to help you extract insights and data from X spaces. Here is/are the command(s) available on the bot.",
        color=discord.Color.blue()
    )
    embed.add_field(name="/download_space <url_to_space>", value="Download and transcribe a Twitter Space. Run the command without the greater than and less than symbols", inline=False)
    embed.add_field(name="Created By", value="[Tobi TheRevolutionary](https://tobitherevolutionary.pythonanywhere.com)", inline=False)
    embed.set_footer(text="Need more help? Contact the creator via the portfolio link!")
    
    await ctx.send(embed=embed)

# Function to analyze the transcription in chunks but return full result
async def analyze_transcription(transcription):
    max_token_length = 128000

    if len(transcription) > max_token_length:
        chunks = chunk_text(transcription, max_token_length)
    else:
        chunks = [transcription]

    final_analysis = ""
    for chunk in chunks:
        user_prompt = f"""
        The following is a transcript of a Twitter Space conversation:
        {chunk}
        """
        
        response = client.chat.completions.create(
            model="chatgpt-4o-latest",  
            messages=[
                {"role": "system", "content": "Analyze this transcription"},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3500,
            temperature=0.5,
        )
        analysis_result = response.choices[0].message.content.strip()
        final_analysis += analysis_result + "\n\n"
        print(final_analysis)

    return final_analysis


# Generate highlights from transcription using OpenAI
async def generate_highlights(transcription):
    prompt = f"""
    Here is a transcription of a Twitter Space conversation:
    {transcription}

    Please extract six key highlights from this conversation that summarize the most important points.
    """
    response = client.chat.completions.create(
        model="chatgpt-4o-latest",
        messages=[{"role": "system", "content": "Extract key highlights"}, {"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.5,
    )
    
    highlights = response.choices[0].message.content.strip().split("\n")
    highlights = [highlight for highlight in highlights if highlight]  # Clean up empty lines

    return highlights[:6]  # Return only the first six highlights

# Helper function to wrap text to fit within the card width
def wrap_text(text, draw, font, max_width):
    words = text.split(' ')
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)
    return lines


# Function to generate highlight cards with proper markdown formatting
def generate_highlight_cards(highlights, output_folder="cards", background_image_path="./background.jpg", num_cards=6):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Adjust font path to point to your local Poppins font file
    font_path = "./poppins_regular.ttf"
    bold_font_path = "./poppins_bold.ttf"
    italic_font_path = "./poppins_italic.ttf"

    try:
        # Open the background image
        img = Image.open(background_image_path).convert("RGBA")
        width, height = img.size

        # Calculate font size relative to image size
        text_font_size = int(height * 0.05)  # 5% of image height
        header_font_size = int(height * 0.06)  # Larger for headers
        footer_font_size = int(height * 0.03)  # 3% of image height

        # Load font with calculated sizes
        font = ImageFont.truetype(font_path, size=text_font_size)
        bold_font = ImageFont.truetype(bold_font_path, size=text_font_size)
        italic_font = ImageFont.truetype(italic_font_path, size=text_font_size)
        header_font = ImageFont.truetype(bold_font_path, size=header_font_size)
        footer_font = ImageFont.truetype(font_path, size=footer_font_size)

    except IOError:
        print("Error loading the font. Make sure the font file is in the correct path.")
        font = ImageFont.load_default()
        bold_font = ImageFont.load_default()
        italic_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()

    # Function to parse markdown and identify styles
    def parse_markdown_and_apply_style(text, draw, font, bold_font, italic_font, header_font, max_text_width):
        lines = []
        y_offset = 100  # Starting y position

        # Handle headers, bold, and italics using regex
        for line in text.splitlines():
            if re.match(r"^#{1,6} ", line):  # Header
                line = line.lstrip("#").strip()
                font_to_use = header_font
            elif "**" in line or "__" in line:  # Bold text
                line = re.sub(r"[*_]{2}", "", line)
                font_to_use = bold_font
            elif "*" in line or "_" in line:  # Italic text
                line = re.sub(r"[*_]", "", line)
                font_to_use = italic_font
            else:  # Normal text
                font_to_use = font

            wrapped_lines = wrap_text(line, draw, font_to_use, max_text_width)
            for wrapped_line in wrapped_lines:
                draw.text((50, y_offset), wrapped_line, font=font_to_use, fill="white")
                y_offset += font.getbbox(wrapped_line)[3] + 10

        return y_offset

    for i, highlight in enumerate(highlights[:num_cards]):
        try:
            # Use the same background image for each card
            img = Image.open(background_image_path).convert("RGBA")
            draw = ImageDraw.Draw(img)

            # Set max text width and starting y position for text
            max_text_width = width - 100

            # Convert markdown to HTML, then to plain text
            html_content = mdn(highlight)
            plain_text = re.sub(r'<[^>]+>', '', html_content)

            # Apply markdown styling and draw the text onto the card
            y_offset = parse_markdown_and_apply_style(plain_text, draw, font, bold_font, italic_font, header_font, max_text_width)

            # Add footer "Cite by Tobi TheRevolutionary"
            footer_text = "Cite by Tobi TheRevolutionary"
            footer_position = (width // 2 - draw.textbbox((0, 0), footer_text, font=footer_font)[2] // 2, height - 80)
            draw.text(footer_position, footer_text, font=footer_font, fill="white")

            # Save the generated card
            card_filename = f"{output_folder}/card_{i+1}.png"
            img.save(card_filename)
            print(f"Card {i+1} generated successfully as {card_filename}!")

        except IOError:
            print(f"Error generating card {i+1}. Please check the background image path.")



# # Example usage:
# highlights = [
#     "# First Highlight\nThis is a **highlight** from the conversation.",
#     "## Second Highlight\nHere's another important point that was discussed.",
#     "Some more text from the **conversation**."
# ]

# generate_highlight_cards(highlights, background_image_path="background_image.png")

# generate_highlight_cards(highlights, background_image_path="background_image.png")


async def summarize_transcription(transcription):
    max_token_length = 128000
    chunks = chunk_text(transcription, max_token_length) if len(transcription) > max_token_length else [transcription]

    final_summary = ""
    for chunk in chunks:
        user_prompt = f"""
        The following is a transcript of a Twitter Space conversation. Provide a brief and concise summary of the key points discussed:
        {chunk}
        """
        
        response = client.chat.completions.create(
            model="chatgpt-4o-latest",
            messages=[
                {"role": "system", "content": "Summarize this transcription"},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
            temperature=0.5,
        )
        summary_result = response.choices[0].message.content.strip()
        final_summary += summary_result + "\n\n"
    
    return final_summary


# Command to download a Twitter Space and transcribe it
@bot.command(name="download_space", description="Download a Twitter Space and transcribe it")
async def download_space(ctx, url: str):
    download_embed = discord.Embed(
    title="Downloading Twitter Space",
    description=f"""
    Downloading the Twitter Space from: {url}

    **Note:** If the downloaded space is too large, it won't be sent to the server due to Discord's file size limitations. 
    However, the transcription and other functions will still be carried out.
    """,
    color=discord.Color.green()
    )
    await ctx.send(embed=download_embed)
    

    try:
        cookies_file = "./cookies.txt"
        timestamp = get_timestamp()
        uuid = get_uuid()
        output_filename = f"twitter_space_{timestamp}_{uuid}"  

        if not os.path.exists(cookies_file):
            await ctx.send("Cookies file not found. Please provide a valid cookies.txt file.")
            return

        command = f"twspace_dl -i {url} -o {output_filename} --input-cookie-file {cookies_file}"
        subprocess.run(command, shell=True, check=True)

        downloaded_file = None
        if os.path.exists(output_filename + ".m4a"):
            downloaded_file = output_filename + ".m4a"
        elif os.path.exists(output_filename + ".mp3"):
            downloaded_file = output_filename + ".mp3"
        else:
            await ctx.send("Error: Could not find the downloaded audio file.")
            return

        await ctx.send(f"Twitter Space downloaded successfully as {downloaded_file}.")
        await ctx.send(file=discord.File(downloaded_file)) 

    except Exception as e:
        await ctx.send(f"Error downloading the Twitter Space: {str(e)}")
        return
    
    transcribe_embed = discord.Embed(
        title="Transcribing twitter space",
        description="Hang on while the bot transribes your twitter space for you.",
        color=discord.Color.blue(),
    )

    await ctx.send(embed=transcribe_embed)

    try:
        result = model.transcribe(downloaded_file)
        transcription = result["text"]
        await ctx.send("Transcription completed ✅")

        timestamp = get_timestamp()
        transcription_pdf_filename = f"transcription_{timestamp}.pdf"
        generate_pdf_from_markdown(transcription, transcription_pdf_filename)
        transcription_complete_markdown = discord.Embed(
            title="Transcription Completed",
            description="Alright, transcription completed.",
            colour=discord.Color.green()
        )
        await ctx.send("Here's the transcription in PDF format, Give us a second while we generate some highlights from the space for you:", file=discord.File(transcription_pdf_filename))

        # Generate highlights and highlight cards
        highlights = await generate_highlights(transcription)
        generate_highlight_cards(highlights)
        for i in range(1, len(highlights) + 1):
            await ctx.send(f"Highlight {i}:", file=discord.File(f"cards/card_{i}.png"))

        # Clean up files after sending
        os.remove(downloaded_file)
        os.remove(transcription_pdf_filename)

        view = View()
        button_analyze = Button(label="Analyze", style=discord.ButtonStyle.primary)
        button_summary = Button(label="Get Summary", style=discord.ButtonStyle.secondary)

        async def button_analyze_callback(interaction):
            await interaction.response.send_message("Analyzing transcription 🤖🤖🤖...")
            analysis_result = await analyze_transcription(transcription)
            plain_analysis_result = markdown_to_plain_text(analysis_result)
            pdf_filename = f"analysis_{timestamp}.pdf"
            generate_pdf_from_markdown(plain_analysis_result, pdf_filename)
            await interaction.channel.send("Analysis completed, here's the PDF:", file=discord.File(pdf_filename))

            os.remove(pdf_filename)  # Delete the analysis PDF after sending it

        async def button_summary_callback(interaction):
            await interaction.response.send_message("Generating summary...🤖🤖🤖")
            max_token_length = 128000
            chunks = chunk_text(transcription, max_token_length) if len(transcription) > max_token_length else [transcription]
            final_summary = ""
            for chunk in chunks:
                response = client.chat.completions.create(
                    model="chatgpt-4o-latest",
                    messages=[{"role": "system", "content": "Summarize this transcription"}, {"role": "user", "content": f"Summarize this transcription:\n{chunk}"}],
                    max_tokens=3500
                )
                summary = response.choices[0].message.content.strip()
                final_summary += summary + "\n\n"

            plain_final_summary = markdown_to_plain_text(final_summary)
            pdf_filename = f"summary_{timestamp}.pdf"
            generate_pdf_from_markdown(plain_final_summary, pdf_filename)
            await interaction.channel.send("Summary completed, here's the PDF:", file=discord.File(pdf_filename))

            os.remove(pdf_filename)  # Delete the summary PDF after sending it

        button_analyze.callback = button_analyze_callback
        button_summary.callback = button_summary_callback

        view.add_item(button_analyze)
        view.add_item(button_summary)

        await ctx.send("You can now analyze the transcription or get a summary:", view=view)

        # Delete the transcription PDF after sending it
        os.remove(transcription_pdf_filename)

    except Exception as e:
        await ctx.send(f"Encountered Error: {str(e)}")

    # Clean up the downloaded audio file after sending
    if os.path.exists(downloaded_file):
        os.remove(downloaded_file)
        os.remove('cards')



bot.run(TOKEN)
