import os
import json
import base64
from glob import glob

class FileInterface:
    def __init__(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.files_dir = os.path.join(script_dir, 'files')

        if not os.path.exists(self.files_dir):
            try:
                os.makedirs(self.files_dir)
            except OSError as e:
                raise OSError(f"Error creating directory '{self.files_dir}': {e}")
        elif not os.path.isdir(self.files_dir):
            raise NotADirectoryError(f"Path '{self.files_dir}' exists but is not a directory.")
        
    def list(self, params=[]):
        try:
            filelist = glob('*.*')
            return dict(status='OK', data=filelist)
        except Exception as e:
            return dict(status='ERROR', data=str(e))

    def get(self, params=[]):
        try:
            filename = params[0]
            if (filename == ''):
                return dict(status='ERROR', data='Nama file tidak boleh kosong')
            fp = open(f"{filename}", 'rb')
            isifile = base64.b64encode(fp.read()).decode()
            fp.close()
            return dict(status='OK', data_namafile=filename, data_file=isifile)
        except Exception as e:
            return dict(status='ERROR', data=str(e))
    
    def upload(self, params=[]):
        try:
            filename = params[0]
            if (filename == ''):
                return dict(status='ERROR', data='Nama file tidak boleh kosong')
            fp = open(filename, 'wb')
            fp.write(base64.b64decode(params[1]))
            return dict(status='OK', data='File berhasil diupload')
        except Exception as e:
            return dict(status='ERROR', data=str(e))
    
    def delete(self, params=[]):
        try:
            filename = params[0]
            if (filename == ''):
                return dict(status='ERROR', data='Nama file tidak boleh kosong')
            os.remove(filename)
            return dict(status='OK', data='File berhasil dihapus')
        except Exception as e:
            return dict(status='ERROR', data=str(e))

if __name__=='__main__':
    f = FileInterface()