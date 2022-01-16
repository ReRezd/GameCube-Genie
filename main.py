import sys
import usb
import usb.core
import usb.backend.libusb1
import usb.util
import PySimpleGUI as sg

# This is a quick and dirty GameCube Controller adapter reader I wrote for a school project
# On windows you must have the libusb0 (v1.2.6.0) driver installed for teh WUP-208 device
# This is untested on Mac
# This is also untested on Linux

# Misc
DEBUG_MODE = False  # Note really used as much as I hoped, this just enable a few debug print statements

# Descriptors of adapter
VENDOR_ID = 0x057E
PRODUCT_ID = 0x0337

# Commands
START_COMMUNICATION_CMD = b'\x13'  # This byte must be sent for communication to start
RUMBLE_CMD = b'\x11'  # Must appeared 4 bytes to the end inorder to ruble a specific controller

# Read buffer
READ_BUFFER = usb.util.create_buffer(37)


def debugLog(msg):
    if DEBUG_MODE is True:
        print(msg)


class GameCubeGenie:
    device = None
    configuration = None
    interface = None

    # End points
    ENDPOINT_IN = None
    ENDPOINT_OUT = None

    IS_RUMBLING = False

    # Sets this class's device var to the adapter is it's found
    def getAdapterDevice(self):
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is None:
            sg.popup_error('NO ADAPTER FOUND!')
            exit()  # Exit te program if the device isnt found
        else:
            self.device = dev

    # Fills the READ_BUFFER var with all data from the adapter - this is call a lot so it is it's own function
    def readEndpoint(self):
        self.ENDPOINT_IN.read(READ_BUFFER, 2000)

    # Toggles rumble on or off for every port
    # Todo: Only rumble the currently selected port
    def toggleRumble(self):
        if self.IS_RUMBLING is True:
            self.ENDPOINT_OUT.write(RUMBLE_CMD + b'\x00\x00\x00\x00')
            self.IS_RUMBLING = False
        else:
            self.ENDPOINT_OUT.write(RUMBLE_CMD + b'\x01\x01\x01\x01')
            self.IS_RUMBLING = True

    # Releases the interface when the program closes
    # I dont know if this is needed but it's good practice
    def release(self):
        usb.util.release_interface(self.device, 0)

    # Main function that starts everything
    # Todo: rename function to something good
    def a(self):
        # Get Adapter Device
        self.getAdapterDevice()
        # Set Configuration
        self.device.set_configuration()
        # Claim the interface so another program cant use the adapter
        usb.util.claim_interface(self.device, 0)
        # Set configuration and interface vars for later use
        configuration = self.device.get_active_configuration()
        interface = configuration[(0, 0)]

        debugLog(interface)  # Debug

        # Looks for the first OUT endpoint - in a GameCube adapter there is only one
        # Allows use to send commands to the adapter
        self.ENDPOINT_OUT = usb.util.find_descriptor(
            interface,
            custom_match= \
                lambda e: \
                    usb.util.endpoint_direction(e.bEndpointAddress) == \
                    usb.util.ENDPOINT_OUT)

        assert self.ENDPOINT_OUT is not None

        # Looks for the first In endpoint - in a GameCube adapter there is only one
        # Allows us to read any & all data from the adapter
        self.ENDPOINT_IN = usb.util.find_descriptor(
            interface,
            custom_match= \
                lambda e: \
                    usb.util.endpoint_direction(e.bEndpointAddress) == \
                    usb.util.ENDPOINT_IN)

        assert self.ENDPOINT_IN is not None

        # In order for the adapter to startup the command 0x13 must be sent before anything else
        self.ENDPOINT_OUT.write(START_COMMUNICATION_CMD)

        # Turns off  all ports rumble
        # This prevents controller from rumbling after a restart of the program
        self.ENDPOINT_OUT.write(RUMBLE_CMD + b'\x00\x00\x00\x00')


# Converts an integer input to a list of binary 1s|0s
# This makes it easy to read multiple buttons being pressed at once
def convertToBinary(input):
    lst = [int(i) for i in list('{0:0b}'.format(input))]

    # The list we created must be reverse to be almost accurate
    rev = lst[::-1]

    # This adds zeros to the end of the list is the list doesn't reach 8 bits long - makes it easier to handle
    # If I wanted to be more efficient I wouldn't run a while ever time we read these but ¯\_(ツ)_/¯
    while len(rev) <= 7:
        rev.append(0)
    return rev


# Every controller has a set of 9 parameters
# This function returns the correct location of the data for a specific port in the READ_BUFFER
# Port can be 1 - 4 | type can be 0 - 8
# Todo: Change type to be 1 - 9
def getOffsetByPortNum(port, type):
    return ((port - 1) * 9) + (type + 1)


# Window Variables
current_Port = 1

# Storing feature of the UI like this make it easier to update them
port1_CB = sg.Checkbox('P1', default=False)
port2_CB = sg.Checkbox('P2', default=False)
port3_CB = sg.Checkbox('P3', default=False)
port4_CB = sg.Checkbox('P4', default=False)

A_Button = sg.Text('')
B_Button = sg.Text('')
X_Button = sg.Text('')
Y_Button = sg.Text('')
Z_Button = sg.Text('')
L_Dig_Button = sg.Text('')
R_Dig_Button = sg.Text('')
Start_Button = sg.Text('')
Dpad_Up_Button = sg.Text('')
Dpad_Down_Button = sg.Text('')
Dpad_Left_Button = sg.Text('')
Dpad_Right_Button = sg.Text('')

Left_Stick_Value = sg.Text('')
Right_Stick_Value = sg.Text('')

Trigger_Value = sg.Text('')

# Returns the next controller to cycle
cycleCurrentPort = {
    1: 2,
    2: 3,
    3: 4,
    4: 1
}


# Updates every check box to show what ports are in use
# Called every cycle
def checkPorts():
    if READ_BUFFER[1] == 16:
        port1_CB.Update(value=True)
    else:
        port1_CB.Update(value=False)

    if READ_BUFFER[10] == 16:
        port2_CB.Update(value=True)
    else:
        port2_CB.Update(value=False)

    if READ_BUFFER[19] == 16:
        port3_CB.Update(value=True)
    else:
        port3_CB.Update(value=False)

    if READ_BUFFER[28] == 16:
        port4_CB.Update(value=True)
    else:
        port4_CB.Update(value=False)


# Updates every button label to show what buttons are pressed
# Called every cycle
def checkButtons():
    A_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 1)])[0] == 1))
    B_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 1)])[1] == 1))
    X_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 1)])[2] == 1))
    Y_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 1)])[3] == 1))

    Start_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 2)])[0] == 1))
    Z_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 2)])[1] == 1))
    R_Dig_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 2)])[2] == 1))
    L_Dig_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 2)])[3] == 1))

    Dpad_Left_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 1)])[4] == 1))
    Dpad_Right_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 1)])[5] == 1))
    Dpad_Down_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 1)])[6] == 1))
    Dpad_Up_Button.update(value=str(convertToBinary(READ_BUFFER[getOffsetByPortNum(current_Port, 1)])[7] == 1))


# Updates every stick value label to show what X & Y value the sticks are reporting
# Called every cycle
def updateStickValues():
    Left_Stick_Value.update(value=('X: ' + str(READ_BUFFER[getOffsetByPortNum(current_Port, 3)]) + "\n" +
                                   'Y: ' + str(READ_BUFFER[getOffsetByPortNum(current_Port, 4)])))

    Right_Stick_Value.update(value=('X: ' + str(READ_BUFFER[getOffsetByPortNum(current_Port, 5)]) + "\n" +
                                    'Y: ' + str(READ_BUFFER[getOffsetByPortNum(current_Port, 6)])))


# Updates the trigger value label to show what amount that the triggers are reporting
# Called every cycle
def updateTriggerValues():
    Trigger_Value.update(value='Right: ' + str(READ_BUFFER[getOffsetByPortNum(current_Port, 7)]) + "\n" +
                               'Left:  ' + str(READ_BUFFER[getOffsetByPortNum(current_Port, 8)]))


# Runs at startup
if __name__ == '__main__':
    gcg = GameCubeGenie()  # create out instance that we'll be using
    sg.theme('DarkAmber')  # I made this at 2am, Im setting it to dark theme

    # Setting up the GUI
    AdapterPortsFrame = sg.Frame('Adapter Ports', [[port1_CB, port2_CB, port3_CB, port4_CB]])
    CurrentControllerFrame = sg.Frame('Current Controller',
                                      [[sg.Text('Displaying Port: ' + str(current_Port), key='currPort')]])

    layout = [
        [sg.Frame('', [[AdapterPortsFrame, CurrentControllerFrame],
                       [sg.Frame('A Button Pressed', [[A_Button]]), sg.Frame('Start Button Pressed', [[Start_Button]])],
                       [sg.Frame('B Button Pressed', [[B_Button]]), sg.Frame('Z Button Pressed', [[Z_Button]])],
                       [sg.Frame('X Button Pressed', [[X_Button]]), sg.Frame('L Button Pressed', [[L_Dig_Button]])],
                       [sg.Frame('Y Button Pressed', [[Y_Button]]), sg.Frame('R Button Pressed', [[R_Dig_Button]])],
                       [sg.Frame('DPad Up Button Pressed', [[Dpad_Up_Button]]),
                        sg.Frame('DPad Down Button Pressed', [[Dpad_Down_Button]])],
                       [sg.Frame('DPad Left Button Pressed', [[Dpad_Left_Button]]),
                        sg.Frame('DPad Right Button Pressed', [[Dpad_Right_Button]])],
                       [sg.Frame('Left Stick Value', [[Left_Stick_Value]]),
                        sg.Frame('Right Stick Value', [[Right_Stick_Value]]),
                        sg.Frame('Trigger Values', [[Trigger_Value]])],
                       [sg.Frame('Buttons', [[sg.Button("Toggle Rumble"), sg.Button("Next Controller Port")]])]
                       ])]
    ]

    window = sg.Window(title="GameCube Genie", layout=layout, margins=(20, 50))

    # Startup the adapter communication
    gcg.a()

    while True:
        event, values = window.read(timeout=10)  # If there is no timeout nothing happens

        gcg.readEndpoint()  # Get updated values form the adapter

        checkPorts()
        checkButtons()
        updateStickValues()
        updateTriggerValues()

        # Button event for rumble
        if event == "Toggle Rumble":
            gcg.toggleRumble()

        # Button event for cycling through ports
        if event == "Next Controller Port":
            current_Port = cycleCurrentPort[current_Port]
            window['currPort'].update(value='Displaying Port: ' + str(current_Port))

        # Make sure everything closes
        if window.was_closed() or event == 'Exit' or window is None:
            gcg.release()
            break
        else:
            window.refresh()

    sys.exit()