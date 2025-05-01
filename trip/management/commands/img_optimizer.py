from image_optimizer import compression, resize
import os
from PIL import Image
import PIL
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db.models import Q
from trip.models import TripScan
from django.conf import settings
import logging



logging.basicConfig(
    filename="logs/img_optimization.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)

COMPRESSED_IMG_FOLDER_PATH = settings.COMPRESSED_IMG_FOLDER_PATH
DB_SAVING_PATH = settings.DB_SAVING_PATH
IMAGE_OPTIMIZER_MAX_RUNTIME_HOUR = settings.IMAGE_OPTIMIZER_MAX_RUNTIME_HOUR

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        started_dt = datetime.now()
        end_dt = started_dt + timedelta(hours=IMAGE_OPTIMIZER_MAX_RUNTIME_HOUR)
        # Get all the scans which doest ends with -min.jpg. That means files which are not optimized.
        # Change the model name here accordingly to exec this for another model

        logging.info(f"started_dt: {started_dt}")
        logging.info(f"end_dt: {end_dt}")

        scans = TripScan.objects.filter(~Q(image__endswith="-min.jpg"), image__isnull=False)

        total_scans_count = scans.count()
        completed_file_count = 0
        failed_count = 0
        failed_reasons = []
        optimization_completed_time = None

        for scan in scans:
            curr_dt = datetime.now()
            optimization_completed_time = curr_dt
            if curr_dt >= end_dt:
                logging.info(f"curr_dt: {curr_dt}")
                logging.info(f"end_dt: {end_dt}")
                logging.info("------------------------Exiting for loop. End time exceeded------------------------")
                break
            
            try:
                # Get the images actual path in the system
                img_full_path = scan.image.path
                name = scan.image.name
                img_name, img_ext = self.extract_file_name_and_ext(name)
                img_new_name = f"{img_name}-min.{img_ext}"
                image = Image.open(img_full_path)
                image = self.exif_transpose(image)
                image.save(img_full_path)

                # Compress img and get file in in memory
                img = compression.compress_image(
                    actual_img=img_full_path,
                    img_name=img_new_name
                )

                # Resize img and get file in in memory
                img = resize.resize(
                    actual_img=img,
                    img_name=img.name,
                    width=100,
                )

                # Save images after compressing. Images will be saving in compressed images folder.
                img_saving_path = f"{COMPRESSED_IMG_FOLDER_PATH}/{img.name}"
                pil_img = Image.open(img)
                pil_img.save(
                    img_saving_path
                )

                # Save the new image name in the db. If image optimize successfully we will rename the img
                # the name will end with -min.jpg. In the db to reflect this we will be saving the data in db.
                path_saving_in_db = f"{DB_SAVING_PATH}/{img.name}"
                scan.image.name = path_saving_in_db
                scan.save()

                os.remove(img_full_path)

                completed_file_count += 1
            except Exception as err:
                # logging.error(f"error occurs in image optimization: {err}")
                # print(f"err: {err}")
                failed_count += 1
                failed_reasons.append(
                    {
                        "error": err,
                        "image_name": scan.image 
                    }
                )
        
        logging.info(f"total_scans_count: {total_scans_count}")
        logging.info(f"completed_file_count: {completed_file_count}")
        logging.error(f"failed_count: {failed_count}")
        logging.error(f"failed_reasons: {failed_reasons}")
        logging.info(f"completed_time: {optimization_completed_time}")
        logging.info(f"========================image optimization is completed========================")
        

    def extract_file_name_and_ext(self, file_name_with_ext):
        filename_and_ext = file_name_with_ext.split(".")
        file_ext = filename_and_ext[-1]
        file_name = "".join(filename_and_ext[:-1])
        return file_name, file_ext

    def exif_transpose(self, img):
        """
        Rotate the image using the exif data of the image. Some images are auto rotating after saving. 
        Because of that converting back the images Position using exif data.
        """
        if not img:
            return img

        exif_orientation_tag = 274

        # Check for EXIF data (only present on some files)
        if (
            hasattr(img, "_getexif")
            and isinstance(img._getexif(), dict)
            and exif_orientation_tag in img._getexif()
        ):
            exif_data = img._getexif()
            orientation = exif_data[exif_orientation_tag]

            # Handle EXIF Orientation
            if orientation == 1:
                # Normal image - nothing to do!
                pass
            elif orientation == 2:
                # Mirrored left to right
                img = img.transpose(PIL.Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                # Rotated 180 degrees
                img = img.rotate(180)
            elif orientation == 4:
                # Mirrored top to bottom
                img = img.rotate(180).transpose(PIL.Image.FLIP_LEFT_RIGHT)
            elif orientation == 5:
                # Mirrored along top-left diagonal
                img = img.rotate(-90, expand=True).transpose(PIL.Image.FLIP_LEFT_RIGHT)
            elif orientation == 6:
                # Rotated 90 degrees
                img = img.rotate(-90, expand=True)
            elif orientation == 7:
                # Mirrored along top-right diagonal
                img = img.rotate(90, expand=True).transpose(PIL.Image.FLIP_LEFT_RIGHT)
            elif orientation == 8:
                # Rotated 270 degrees
                img = img.rotate(90, expand=True)

        return img
