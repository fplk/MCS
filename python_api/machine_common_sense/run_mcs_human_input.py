import sys
from machine_common_sense.mcs import MCS
from machine_common_sense.mcs_action import MCS_Action
from machine_common_sense.mcs_action_keys import MCS_Action_Keys
from machine_common_sense.mcs_action_api_desc import MCS_Action_API_DESC

if len(sys.argv) < 3:
    print('Usage: python run_mcs_human_input.py <mcs_unity_build_file> <mcs_config_json_file>')
    sys.exit()

# variables
commandList = []

# class to contain possible commands and keys
class command:
    def __init__(self, name, key, desc):
        self.name = name
        self.key = key
        self.desc = desc

# Define all the possible human input commands
def build_commands(): 
    for action in MCS_Action:
        commandList.append(command(action.value, MCS_Action_Keys[action.name].value, MCS_Action_API_DESC[action.name].value))

# Display all the possible commands to the user along with key mappings
def print_commands():
    print("--------------- Available Commands ---------------")
    for commandListItem in commandList:
        print("*******************")
        print("Command: " + commandListItem.name)
        print("Usage: " + commandListItem.desc)
        print("ShortcutKey: " + commandListItem.key)
        print("*******************")

    print("Example commands: ")
    print("MoveAhead")
    print("RotateLook, rotation=45, horizon=15")
    print(" ")
    print("Enter 'help' to print the commands again.")
    print("Enter 'exit' to exit the program.")
    print(" ")
    print("------------------ End Commands ------------------")

# Check to see if a string is a float before converting
def isFloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

# Execute Input Commands until the user exits the system
def input_commands(controller): 
    print('Enter your command:')
    userInput = input().split(',')

    if(userInput[0] == 'exit'):
        print("Exiting Human Input Mode")
        return

    if(userInput[0] == 'help'):
        print_commands()
        return input_commands(controller)

    # Check for shortcut key, if attempted shortcut key, map and check valid key
    try:
        if len(userInput[0]) == 1:
            userInput[0] = MCS_Action[MCS_Action_Keys(userInput[0] ).name].value
    except:
        print("You entered an invalid shortcut key, please try again. (Type 'help' to display commands again)")
        print("You entered: " + userInput[0])
        return input_commands(controller)

    print('You entered command: ')
    print(*userInput)

    # Check action is available, before executing and defaulting to a pass
    try:
        actionCheck = MCS_Action(userInput[0]).name
    except:
        print("You entered an invalid command, please try again.  (Type 'help' to display commands again)")
        return input_commands(controller)
 
    # Run commands that have no parameters
    if len(userInput) < 2:
        output = controller.step(userInput[0])
        return input_commands(controller)
    else:
        # Create Params List
        try:
            params = {}
            for param in userInput[1:]:
                paramKey, paramValue = param.split('=')
                if isFloat(paramValue.strip()):
                    params[paramKey.strip()] = float(paramValue.strip())
                else: 
                    params[paramKey.strip()] = paramValue.strip()
        except:
            print("ERROR: Parameters should be separated by commas, and look like this example: rotation=45")
            return input_commands(controller)

        output = controller.step(userInput[0], **params)
        return input_commands(controller)

# Run scene loaded in the config data
def run_scene(controller, config_data):
    build_commands()
    print_commands()

    output = controller.start_scene(config_data)

    input_commands(controller)

    sys.exit()

def main():
    config_data, status = MCS.load_config_json_file(sys.argv[2])

    if status is not None:
        print(status)
        exit()

    controller = MCS.create_controller(sys.argv[1], debug='terminal')

    config_file_path = sys.argv[2]
    config_file_name = config_file_path[config_file_path.rfind('/'):]

    if 'name' not in config_data.keys():
        config_data['name'] = config_file_name[0:config_file_name.find('.')]

    run_scene(controller, config_data)

if __name__ == "__main__":
    main()
