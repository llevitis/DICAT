import os
import sys
import xml.etree.ElementTree as ET
import subprocess
import re
import shutil
from shutil import move

"""
Test whether PyDICOM module exists and import it.
Notes:
- in the past, PyDICOM was imported using "import pydicom as dicom"
- newer versions of the PyDICOM module are imported using "import dicom"
- returns true if the PyDICOM was imported, false otherwise
"""
# create a boolean variable that returns True if PyDICOM was imported, False if not
use_pydicom = False
try:
    import pydicom as dicom
    # set use_pydicom to true as PyDICOM was found and imported
    use_pydicom = True
except ImportError:
    # try importing newer versions of PyDICOM
    try:
        import dicom
        # set use_pydicom to true as PyDICOM was found and imported
        use_pydicom = True
    except ImportError:
        # set use_pydicom to false as PyDICOM was not found
        use_pydicom = False

"""
Determine which anonymizer tool will be used by the program:
- PyDICOM python module if found and imported
- DICOM toolkit if found on the filesystem
"""
def FindAnonymizerTool():
    # If found PyDICOM was found, PyDICOM will be used and returned
    if use_pydicom == True:
        return 'PyDICOM'
    # Else if dcmdump executable exists, the DICOM toolkit will be used and returned
    elif TestExecutable('dcmdump') == True:
        return 'DICOM_toolkit'
    # Else, no anonymizer tool were found and return false
    else:
        return False

"""
Test if an executable exists.
Returns True if executable exists, False if not found.
"""
# TODO: find a way to not display dcmdump help in the terminal
def TestExecutable(executable):
    # try running the executable
    try:
        subprocess.call([executable])
        return True
    except OSError as e:
        return False

###########################################
# Grep recursively all DICOMs from folder #
###########################################
def GrepDicomsFromFolder(dicom_folder):

    # Initialize list of DICOMs and subdirectories
    dicoms_list  = []
    subdirs_list = []
    # Grep DICOM files recursively and insert them in dicoms_list
    # Same for subdirectories
    # Regular expression to identify files that are not DICOM.
    pattern = re.compile("\.bmp$|\.png$|\.zip$|\.txt$|\.jpeg$|\.pdf$|\.DS_Store")
    for root, subdirs, files in os.walk(dicom_folder, topdown=True):
        if len(files) != 0 or len(subdirs) != 0:
            for dicom_file in files:
                if pattern.search(dicom_file) is None:
                    dicoms_list.append(os.path.join(root,dicom_file))
            for subdir in subdirs:
                subdirs_list.append(subdir)
        else:
            sys.exit('Could not find any files in ' + dicom_folder)

    return dicoms_list, subdirs_list



###################################
# Read DICOM fields from XML file #
###################################
def Grep_DICOM_fields(xml_file):
    xmldoc = ET.parse(xml_file)
    dicom_fields = {}
    for item in xmldoc.findall('item'):
        name = item.find('name').text
        description = item.find('description').text
        editable = True if (item.find('editable').text=="yes") else False #kr#
        dicom_fields[name] = {"Description": description, "Editable": editable} #kr#
        #dicom_fields[name] = {"Description": description}
    return dicom_fields


"""
Grep value from DICOM fields using PyDICOM
"""
def Grep_DICOM_values_PyDicom(dicom_folder, dicom_fields):
    # Grep first DICOM of the directory
    # TODO: Need to check if file is DICOM though, otherwise go to next one
    (dicoms_list, subdirs_list) = GrepDicomsFromFolder(dicom_folder)
    dicom_file = dicoms_list[0]

    # Read DICOM file using PyDICOM
    dicom_dataset = dicom.read_file(dicom_file)

    # Grep information from DICOM header and store them
    # into dicom_fields dictionary under flag Value
    # Dictionnary of DICOM values to be returned
    for name in dicom_fields:
        try:
            dicom_fields[name]['Value'] = dicom_dataset.data_element(dicom_fields[name]['Description']).value
        except:
            continue    

    return dicom_fields


"""
Grep value from DICOM fields using dcmdump from DICOM toolkit
"""
def Grep_DICOM_values(dicom_folder, dicom_fields):
    # Grep first DICOM of the directory
    # TODO: Need to check if file is DICOM though, otherwise go to next one
    (dicoms_list, subdirs_list) = GrepDicomsFromFolder(dicom_folder)
    dicom_file = dicoms_list[0]
    
    # Grep information from DICOM header and store them
    # into dicom_fields dictionary under flag Value
    for name in dicom_fields:
        dump_cmd = "dcmdump -ml +P " + name + " -q " + dicom_file
        result = subprocess.check_output(dump_cmd, shell=True)
        tmp_val = re.match(".+\[(.+)\].+", result)
        if tmp_val:
            value = tmp_val.group(1)
            dicom_fields[name]['Value'] = value
    return dicom_fields


######################################
# Run dcmmodify on all fields to zap using PyDicom recursive wrapper#
######################################
def Dicom_zapping_PyDicom(dicom_folder, dicom_fields):

    print "Hello!"
    # Grep all DICOMs present in directory
    (dicoms_list, subdirs_list) = GrepDicomsFromFolder(dicom_folder)

    # Create an original_dcm and anonymized_dcm directory in the DICOM folder, as well as subdirectories
    (original_dir, anonymize_dir) = createDirectories(dicom_folder, dicom_fields, subdirs_list)

    # Move DICOMs into the original_directory created
    for dicom in dicoms_list:
        shutil.copy(dicom, anonymize_dir)
        move(dicom, original_dir)

#TODO: finish implementing this
    for root, dirs, files in os.walk(anonymize_dir):
        if len(files)!=0:
            for dicom_file in files:
                print 'anonymizing->'+dicom_file
                #actual_zapping(os.path.join(root, dicom_file), dicom_fields)

    return anonymize_dir, original_dir

######################################
# Actual zapping method #
######################################
def actual_zapping(dicom_file, dicom_fields):

    dicom_dataset = dicom.read_file(dicom_file)

    for field_values in dicom_fields.values():
        if field_values['Editable'] is True:
            try:
                dicom_dataset.data_element(field_values['Description']).value=''
                
            except:
                continue
    dicom_dataset.save_as(dicom_file)

######################################
# Run dcmmodify on all fields to zap #
######################################
def Dicom_zapping(dicom_folder, dicom_fields):
    
    # Grep all DICOMs present in directory
    (dicoms_list, subdirs_list) = GrepDicomsFromFolder(dicom_folder)

    # Create an original_dcm and anonymized_dcm directory in the DICOM folder, as well as subdirectories
    (original_dir, anonymize_dir)  = createDirectories(dicom_folder, dicom_fields, subdirs_list)

    # Initialize the dcmodify command
    modify_cmd = "dcmodify "
    changed_fields_nb = 0
    for name in dicom_fields:
        # Grep the new values
        new_val = ""
        if 'Value' in dicom_fields[name]:
            new_val = dicom_fields[name]['Value']

        # Run dcmodify if update is set to True
        if not dicom_fields[name]['Editable'] and 'Value' in dicom_fields[name]:
            modify_cmd        += " -ma \"(" + name + ")\"=\" \" "
            changed_fields_nb += 1
        else:
            if dicom_fields[name]['Update'] == True:
                modify_cmd        += " -ma \"(" + name + ")\"=\"" + new_val + "\" "
                changed_fields_nb += 1

    # Loop through DICOMs and
    # 1. move DICOM files into anonymized_dir (we'll move the .bak file into original_dcm once dcmodify has been run)
    # 2. run dcmodify
    # 3. move .bak file into original directory
    for dicom in dicoms_list:
        original_dcm  = dicom.replace(dicom_folder, original_dir)
        anonymize_dcm = dicom.replace(dicom_folder, anonymize_dir)
        orig_bak_dcm  = anonymize_dcm + ".bak"
        if changed_fields_nb > 0:
            move(dicom, anonymize_dcm)
            subprocess.call(modify_cmd + anonymize_dcm, shell=True)
            if os.path.exists(orig_bak_dcm):
                move(orig_bak_dcm, original_dcm)
        else:
            move(dicom, original_dcm)

    # If anonymize and original folders exist, zip them
    if os.path.exists(anonymize_dir) and os.path.exists(original_dir):
        original_zip  = zipDicom(original_dir)
        anonymize_zip = zipDicom(anonymize_dir)
    else:
        sys.exit('Failed to anonymize data')

    # If archive anonymized and original DICOMs found, remove subdirectories in root directory
    if os.path.exists(anonymize_zip) and os.path.exists(original_zip):
        for subdir in subdirs_list:
            shutil.rmtree(dicom_folder + os.path.sep + subdir)

    return original_zip, anonymize_zip


"""
Create two directories in the main DICOM folder:
- one to copy over the original DICOM folders (not anonymized)
- one for the anonymized DICOM files
"""
def createDirectories(dicom_folder, dicom_fields, subdirs_list):

    # Create an original_dcm and anonymized_dcm directory in the DICOM folder, as well as subdirectories
    original_dir  = dicom_folder + os.path.sep + dicom_fields['0010,0010']['Value']
    anonymize_dir = dicom_folder + os.path.sep + dicom_fields['0010,0010']['Value'] + "_anonymized"
    os.mkdir(original_dir,  0755)
    os.mkdir(anonymize_dir, 0755)
    # Create subdirectories in original and anonymize directory, as found in DICOM folder
    for subdir in subdirs_list:
        os.mkdir(original_dir  + os.path.sep + subdir,  0755)
        os.mkdir(anonymize_dir + os.path.sep + subdir,  0755)

    return original_dir, anonymize_dir


def zipDicom(directory):
    archive = directory + '.zip'

    if (os.listdir(directory) == []):
        sys.exit("The directory " + directory + " is empty and will not be archived.")
    else:
        shutil.make_archive(directory, 'zip', directory)

    if (os.path.exists(archive)):
        shutil.rmtree(directory)
        return archive
    else:
        sys.exit(archive + " could not be created.")


### Test function
def anonymize_folder(folder_name):
    print folder_name
    dict_data_fields={'Name':'Ayan','Age':25}
    if not os.path.exists(folder_name):
        sys.exit('The directory selected does not exist....')
    else:
        return dict_data_fields
        
