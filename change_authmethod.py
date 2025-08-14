import sys
import subprocess

# Get the authentication method from command-line input
authmethod = sys.argv[1]

# Supported types
authmethods = ['OpenAPI_auth_method_5G_AKA', 'OpenAPI_auth_method_EAP_AKA_PRIME', 'OpenAPI_auth_method_EAP_TLS']
authtypes = ['OpenAPI_auth_type_5G_AKA', 'OpenAPI_auth_type_EAP_AKA_PRIME', 'OpenAPI_auth_type_EAP_TLS']
# Files to update
f1 = "udr//nudr-handler.c"
f2 = "udm//nudr-handler.c"
f3 = "ausf//nudm-handler.c"
f4 = "amf//nausf-handler.c"

# Constant to search for in files
constant0 = "AuthenticationSubscription.authentication_method ="
constant1 = "AuthenticationSubscription->authentication_method !="
constant2 = "udm_ue->auth_type ="
constant3 = "AuthenticationInfoResult->auth_type !="
constant4 = "UeAuthenticationCtx->auth_type !="


# Replacement function that preserves indentation
def replace(filename,constant, new_value):
    with open(filename, 'r') as file:
        lines = file.readlines()

    with open(filename, 'w') as file:
        for line in lines:
            if constant in line:
                leading_spaces = line[:line.index(constant)]
                line = f"{leading_spaces}{constant} {new_value}\n"
            file.write(line)  # <<-- moved inside loop
    
# Main logic
if authmethod == "5G_AKA":
    replace(f1,constant0, authmethods[0])
    replace(f2,constant1, authmethods[0])
    replace(f2,constant2, authtypes[0])
    replace(f3,constant3, authmethods[0])
    replace(f4,constant4, authtypes[0])
    build_dir = "/home/gcore1/open5gs/build"  # <- adjust this to your actual build dir
    subprocess.run(["ninja", "install"], cwd=build_dir)
    print(f"Successfully updated auth_method to {authmethod} in all files.")
elif authmethod == "EAP_AKA":
    replace(f1,constant0, authmethods[1])
    replace(f2,constant1, authmethods[1])
    replace(f2,constant2, authtypes[1])
    replace(f3,constant3, authmethods[1])
    replace(f4,constant4, authtypes[1])
    build_dir = "/home/gcore1/open5gs/build"  # <- adjust this to your actual build dir
    subprocess.run(["ninja", "install"], cwd=build_dir)
    print(f"Successfully updated auth_method to {authmethod} in all files.")
elif authmethod == "EAP_TLS":
    replace(f1,constant0, authmethods[2])
    replace(f2,constant1, authmethods[2])
    replace(f2,constant2, authtypes[2])
    replace(f3,constant3, authmethods[2])
    replace(f4,constant4, authtypes[2])
    build_dir = "/home/gcore1/open5gs/build"  # <- adjust this to your actual build dir
    subprocess.run(["ninja", "install"], cwd=build_dir)
    print(f"Successfully updated auth_method to {authmethod} in all files.")
else:
    print(f"Unsupported auth type: {authmethod}")
    print(f"Supported options: {authmethod}")
