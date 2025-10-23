To have your server script run on startup before a user signs in, you need to set it up as a **system service** (on Windows and Linux) or a **launch daemon** (on macOS). This is different from a simple "login item," which only runs after a user logs in.

Here’s how to do it for each operating system.

-----

### \#\# Windows: Using Task Scheduler

On Windows, the best tool for this is the **Task Scheduler**, which can run tasks at boot using the high-privilege `SYSTEM` account.

1.  **Open Task Scheduler:** Press `Win + R`, type `taskschd.msc`, and press Enter.

2.  **Create a New Task:** In the Actions pane on the right, click "Create Task...".

3.  **General Tab:**

      * **Name:** Give it a clear name, like "Remote iOS Server".
      * **Security Options:** Click "Change User or Group...", type `SYSTEM`, and click OK. This is the key step to make it run before login.
      * Select "Run whether user is logged on or not" and check the "Run with highest privileges" box.

4.  **Triggers Tab:**

      * Click "New...".
      * For "Begin the task:", select **"At startup"**.
      * Click OK.

5.  **Actions Tab:**

      * Click "New...".
      * **Action:** "Start a program".
      * **Program/script:** Browse to your Python executable, specifically `pythonw.exe`. Using `pythonw.exe` is crucial as it runs the script silently in the background without a console window popping up. A typical path is `C:\Python39\pythonw.exe`.
      * **Add arguments (optional):** Enter the full path to your Python script (e.g., `C:\Users\YourUser\Documents\windows_server.py`).
      * **Start in (optional):** Enter the directory where your script is located (e.g., `C:\Users\YourUser\Documents\`). This prevents issues with relative paths.

6.  **Conditions/Settings Tabs:** You can generally leave these as default, but you might want to uncheck "Stop the task if it runs longer than:" in the Settings tab.

7.  **Save:** Click OK to save the task. It will now run automatically every time the PC boots.

-----

### \#\# macOS: Using `launchd`

On macOS, the system service manager is called `launchd`. You configure it by creating a special `.plist` file in a system directory.

1.  **Create a `.plist` File:** Create a new file named `com.yourcompany.remoteserver.plist` (the name should be unique). Paste the following XML content into it, updating the paths as needed.

    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.yourcompany.remoteserver</string>
        <key>ProgramArguments</key>
        <array>
            <string>/usr/bin/python3</string>
            <string>/Users/YourUser/Documents/mac_server.py</string>
        </array>
        <key>RunAtLoad</key>
        <true/>
        <key>KeepAlive</key>
        <true/>
    </dict>
    </plist>
    ```

      * **`ProgramArguments`**: Make sure the paths to both `python3` and your script are correct.
      * **`RunAtLoad`**: Tells `launchd` to start the script at boot.
      * **`KeepAlive`**: Tells `launchd` to automatically restart your script if it ever crashes.

2.  **Move the File:** Open Finder, press `Cmd+Shift+G`, and go to the folder `/Library/LaunchDaemons`. You need administrator privileges to modify this folder. Copy your `.plist` file here.

      * **Important:** Use `/Library/LaunchDaemons` to run as root before login. Do **not** use `~/Library/LaunchAgents`, which is for user-specific agents that run after login.

3.  **Load the Daemon:** Open the **Terminal** and run the following command to load your new service.

    ```bash
    sudo launchctl load /Library/LaunchDaemons/com.yourcompany.remoteserver.plist
    ```

Your script is now registered with the system and will start automatically on every boot.

-----

### \#\# Linux (Raspberry Pi OS): Using `systemd`

Modern Linux distributions, including Raspberry Pi OS, use `systemd` to manage services. You'll create a `.service` file to define how your script should run.

1.  **Create a `.service` File:** In a terminal, create a new service file.

    ```bash
    sudo nano /etc/systemd/system/remote-ios-server.service
    ```

2.  **Add Configuration:** Paste the following content into the file, updating the path to your script.

    ```ini
    [Unit]
    Description=iOS Remote Input Server
    After=network.target

    [Service]
    ExecStart=/usr/bin/python3 /home/pi/your_script.py
    Restart=always
    User=pi

    [Install]
    WantedBy=multi-user.target
    ```

      * **`After=network.target`**: **This is essential.** It ensures the service only starts after the network is connected, which your server needs.
      * **`ExecStart`**: The full path to Python and your script.
      * **`Restart=always`**: Automatically restarts the script if it crashes.
      * **`User=pi`**: Runs the script as the `pi` user. If your script requires root (like the Wayland `uinput` example), you might need to change this to `User=root` or omit the line entirely.

3.  **Enable the Service:** Save the file (`Ctrl+O`, then `Ctrl+X` in `nano`). Now, enable and start the service with these commands:

    ```bash
    # Reload the systemd manager configuration
    sudo systemctl daemon-reload

    # Enable your service to start on boot
    sudo systemctl enable remote-ios-server.service

    # Start the service immediately to test it
    sudo systemctl start remote-ios-server.service
    ```

Your server will now run as a background service every time the Raspberry Pi boots up.
