# Pymegle

Pymegle is an unofficial API for [Omegle's](https://www.omegle.com/) text chat using asyncio. It provides an interface 
for connecting to text chats and asynchronous event handling. This package also comes bundled with a full-featured user client that can be run in the console.

DISCLAIMER: This software is not intended to be used for spam or other disruptive/malicious activities. Please abide by 
Omegle's terms of service.

# Installation

Pymegle can be installed from PyPi using the following command:
```
pip install pymegle
```

# Starting Out

The simplest usage of this package is interacting with the user client. It can be run using the following code.

**NOTE:** Many consoles were not designed with asynchronous operation in mind and as a result may experience issues 
when running the interactive client. PyCharm's _Python Console_ and the Windows command prompt tend to perform the best.
```python
import pymegle

pymegle.run_user_clent()
```
The user client recreates the Omegle browser experience in the console, showcasing what can be done with this API.

# Basic Usage

The `OmegleChat` class is the basic handler for text chat interactions. It represents a single chat between the client 
(user) and a partner. It can be inherited to handle various events, such as receiving messages.

For this example, we will make a simple dice roller that responds to a command given by the partner and sends a result.

```python
import pymegle
import random

class DiceRoller(pymegle.OmegleChat):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    
    # Automatically add 'diceroller' to the chat request's interests
    self.interests.add("diceroller")
   
  # This coroutine is called when the client successfully connects to a partner
  async def on_connected(self, i):
    # Send a greeting message
    await self.send_message("Hello! Type /roll and I will roll a 6 sided die for you")
  
  # This coroutine is called when the partner sends a message
  async def on_message(self, m):
    # Check if the message matches the specified command
    if m == "/roll":
      await self.send_message("🎲 Rolling...")
      await self.type_message(f"Result: {random.randrange(1, 7)}")
```

The above chat can then be run by doing:
```python
chat = DiceRoller()
chat.start()
```

Then, connect to Omegle with `diceroller` in the interests to test it.
