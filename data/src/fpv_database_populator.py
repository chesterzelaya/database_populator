import os
import json
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QLineEdit, QPushButton, QTextEdit, QMessageBox, QScrollArea, QCheckBox, QDialog, QDialogButtonBox,
                             QProgressBar, QTabWidget)
from PyQt6.QtCore import Qt, QTimer, QRunnable, QThreadPool, pyqtSignal, QObject
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
import pickle

# Load environment variables
load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.droneFPVPartPicker

def query_perplexity(prompt, model="llama-3.1-sonar-huge-128k-online", max_tokens=4000):
    API_URL = "https://api.perplexity.ai/chat/completions"
    API_KEY = os.getenv("PERPLEXITY_API_KEY")
    
    if not API_KEY:
        raise ValueError("PERPLEXITY_API_KEY not found in environment variables")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a specialized web scraping assistant for FPV drone parts. You are meticulous and precise, all the information you provide must be verified and validated. You are not allowed to make up any information. If you are unsure of something, try to find the most accurate answer."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        
        # Remove ```json and ``` from the response
        content = content.replace("```json", "").replace("```", "").strip()
        
        return content
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Perplexity API: {str(e)}")
        return None

def send_to_mongodb(data, category):
    collection = db[category]
    result = collection.insert_one(data)
    print(f"Inserted document into '{category}' collection with ID: {result.inserted_id}")
    return result.inserted_id

class Worker(QRunnable):
    class Signals(QObject):
        result = pyqtSignal(object)
        finished = pyqtSignal()
        error = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = Worker.Signals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.error.emit(str(e))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

class ProductTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Category selection
        category_layout = QHBoxLayout()
        category_label = QLabel("Category:")
        self.category_combo = QComboBox()
        categories = [
            "frames",
            "propellers",
            "motors",
            "batteries",
            "flightcontrollers",
            "escs",
            "videotransmitters",
            "fpvcameras",
            "receivers"
        ]
        self.category_combo.addItems(categories)
        category_layout.addWidget(category_label)
        category_layout.addWidget(self.category_combo)
        self.layout.addLayout(category_layout)

        # Product name input
        product_layout = QHBoxLayout()
        product_label = QLabel("Product Name:")
        self.product_input = QLineEdit()
        product_layout.addWidget(product_label)
        product_layout.addWidget(self.product_input)
        self.layout.addLayout(product_layout)

        # Get Product Info button
        self.get_info_button = QPushButton("Get Product Info")
        self.get_info_button.clicked.connect(self.get_info)
        self.layout.addWidget(self.get_info_button)

        # Split bottom area
        bottom_layout = QHBoxLayout()

        # JSON display
        self.json_text = QTextEdit()
        bottom_layout.addWidget(self.json_text, 1)

        # Compatibility tags
        compatibility_widget = QWidget()
        compatibility_layout = QVBoxLayout()
        compatibility_widget.setLayout(compatibility_layout)

        self.compatibility_checkboxes = {}
        self.compatibility_data = {
            "frames": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Size": ["1.5 inch", "2 inch", "2.5inch", "3 inch", "3.5 inch", "4 inch", "5 inch", "7 inch", "10 inch"],
                "Motor Mount": ["3-M1.4-φ6.6mm","3-16x19mm","3-25x25mm","4-M2-12x12mm", "4-16x16mm", "4-19x19mm", "4-25x25mm", "4-30x30mm", "4-40x40mm"],
                "Stack Mount": ["20x20mm", "25.5x25.5mm", "30.5x30.5mm", "36x36mm"],
                "Max Prop Size": ["1.5 inch", "1.77 inch", "2 inch", "2.5 inch", "3 inch", "3.5 inch", "5 inch", "7 inch", "10 inch"],
                "VTX Mount": ["20x20mm", "25.5x25.5mm"],
                "Camera Size": ["14mm", "19mm", "21mm","28mm"],
                "Battery Mount": ["20x20mm", "30x30mm", "40x40mm"],
                "Arm Thickness": ["4mm", "5mm", "6mm", "8mm"],
                "Weight Class": ["Lightweight", "Medium", "Heavy"],
                "Material": ["Carbon Fiber", "Plastic", "Aluminum"]
            },
            "propellers": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Diameter": ["1.77 inch", "2 inch", "3 inch", "3.5 inch", "4 inch", "5 inch", "6 inch", "7 inch"],
                "Pitch": ["1.5 inch", "2 inch", "3 inch", "4 inch", "5 inch", "6 inch"],
                "Bore": ["1mm", "1.5mm", "3mm", "5mm", "6mm"],
                "Rotation": ["CW", "CCW"],
                "Blade Count": ["2-blade", "3-blade", "4-blade", "5-blade"],
                "Mounting Type": ["Press Fit", "Threaded", "T-Mount"]
            },
            "motors": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Stator Size": ["0702","1103", "1204", "1306", "1408", "1506", "2205", "2206", "2207", "2306", "2307", "2405", "2506", "2507", "2508"],
                "Shaft Diameter": ["1.0mm","1.5mm", "2mm", "3mm", "4mm", "5mm"],
                "Mounting Pattern": ["3-M1.4-φ6.6mm","3-16x19mm","3-25x25mm","4-M2-12x12mm", "4-M3-16x16mm", "4-19x19mm", "4-25x25mm", "4-30x30mm", "4-40x40mm"],
                "KV Rating": ["1300KV", "1700KV", "1800KV", "2300KV", "2600KV", "1960KV", "3000KV", "4000KV", "22000KV", "23000KV", "25000KV", "26000KV", "28000KV", "30000KV", "46000KV"],
                "Prop Mounting Type": ["Press Fit", "Threaded", "T-Mount"],
                "Prop Compatibility": ["1.23", "3 inch", "4 inch", "5 inch", "6 inch", "7 inch"],
                "Voltage": ["1S","2S", "3S", "4S", "5S", "6S"]
            },
            "batteries": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Voltage": ["1S", "2S", "3S", "4S", "5S", "6S"],
                "Capacity": ["300mAh", "450mAh", "650mAh", "850mAh", "1000mAh", "1300mAh", "1500mAh", "2200mAh"],
                "Discharge Rate": ["25C", "50C", "75C", "100C", "150C"],
                "Connector": ["XT30", "XT60", "XT90", "PH2.0", "BT2.0", "JST"],
                "Form Factor": ["Standard", "Long", "Square", "Flat"]
            },
            "flightcontrollers": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Size": ["16x16mm", "20x20mm", "25.5x25.5mm", "30.5x30.5mm", "36x36mm"],
                "Processor": ["F4", "F7", "H7"],
                "Voltage": ["1S", "2S", "3S", "4S", "5S", "6S"],
                "Gyro": ["MPU6000", "ICM20602", "BMI270"],
                "UART Count": ["4", "6", "8", "10+"],
                "Firmware": ["Betaflight", "INAV", "Ardupilot", "KISS"],
                "Motor Protocol": ["DShot300", "DShot600", "DShot1200", "Oneshot", "Multishot", "Serial"],
                "Receiver Protocol": ["FrSky", "Spektrum", "FlySky", "Crossfire", "ExpressLRS"],
                "Features": ["Stack", "PDB", "ESC", "OSD", "VTX", "SD Card", "Telemetry"]
            },
            "escs": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Size": ["16x16mm", "20x20mm", "25.5x25.5mm", "30.5x30.5mm", "36x36mm"],
                "Current Rating": ["20A", "30A", "40A", "50A", "60A", "70A", "80A", "90A", "100A"],
                "Voltage": ["2-4S", "3-6S", "2-8S"],
                "Battery Connector": ["XT30", "XT60", "XT90", "PH2.0", "BT2.0", "JST"],
                "Firmware": ["BLHeli_S", "BLHeli_32", "KISS"],
                "Protocol": ["DShot300", "DShot600", "DShot1200", "Multishot", "Oneshot125"]
            },
            "videotransmitters": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Frequency": ["5.8GHz", "2.4GHz", "1.3GHz"],
                "Resolution": ["720p", "1080p", "4K"],
                "Refresh Rate": ["30fps", "60fps", "120fps"],
                "Latency": ["10ms", "20ms", "30ms", "40ms", "50ms"],
                "Range": ["100m", "200m", "300m", "400m", "500m"],
                "Power Output": ["25mW", "200mW", "500mW", "800mW", "1W", "2W"],
                "Video Format": ["Analog", "DJI HD", "HDZero", "Walksnail Avatar"],
                "SD Card": ["Yes", "No"],
                "Mount Size": ["20x20mm", "25.5x25.5mm", "30.5x30.5mm", "36x36mm"],
                "Voltage": ["3.3V", "5V", "5-36V"],
                "Antenna Connector": ["UFL", "MMCX", "SMA"],
                "Smart Audio": ["Yes", "No"]
            },
            "vtxantenna": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Frequency": ["5.8GHz", "2.4GHz", "1.3GHz"],
                "Range": ["100m", "200m", "300m", "400m", "500m"],
                "Power Output": ["25mW", "200mW", "500mW", "800mW", "1W", "2W"],
                "Polarization": ["Linear", "Circular (LHCP)", "Circular (RHCP)"],
                "Environment": ["Indoor", "Outdoor"],
                "Antenna Connector": ["UFL", "MMCX", "SMA", "I-PEX"],
                "Smart Audio": ["Yes", "No"]
            },
            "fpvcameras": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Sensor Size": ["1/3 inch", "1/2.7 inch", "1/2 inch", "1/1.8 inch"],
                "Size": ["14mm", "19mm", "21mm", "28mm"],
                "Resolution": ["700TVL", "1000TVL", "1200TVL", "1800TVL"],
                "Lens": ["1.8mm", "2.1mm", "2.5mm"],
                "FOV": ["120°", "135°", "150°", "170°"],
                "Voltage": ["3.3V", "5V", "5-36V"]
            },
            "receivers": {
                "Drone Type": ["Cinewhoop", "Freestyle", "Racing", "Long Range", "Micro/Toothpick", "Tiny Whoop"],
                "Protocol": ["FrSky", "Spektrum", "FlySky", "Crossfire", "ExpressLRS"],
                "Telemetry": ["Yes", "No"],
                "Antenna Type": ["Dipole", "Diversity", "Ceramic", "Cloverleaf"],
                "Voltage": ["3.3V", "5V"],
                "Polarization": ["Linear", "Circular (LHCP)", "Circular (RHCP)"],
                "Environment": ["Indoor", "Outdoor"],
                "Antenna Connector": ["SMA", "RP-SMA", "U.FL", "MMCX"]
            }
        }

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(compatibility_widget)
        bottom_layout.addWidget(scroll_area, 1)

        self.layout.addLayout(bottom_layout)

        # Refresh button
        self.refresh_button = QPushButton("Refresh Compatibility")
        self.refresh_button.clicked.connect(self.refresh_compatibility)
        self.layout.addWidget(self.refresh_button)

        # Send to MongoDB button
        self.send_to_db_button = QPushButton("Send to MongoDB")
        self.send_to_db_button.clicked.connect(self.send_to_db)
        self.layout.addWidget(self.send_to_db_button)

        # Add New Entry button
        self.add_entry_button = QPushButton("Add New Compatibility Entry")
        self.add_entry_button.clicked.connect(self.add_new_entry)
        self.layout.addWidget(self.add_entry_button)

        # Connect category change to update compatibility checkboxes
        self.category_combo.currentTextChanged.connect(self.update_compatibility_checkboxes)

        # Add progress bar
        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)
        self.progress_bar.hide()

        # Cache directory
        self.cache_dir = "data/cache"
        os.makedirs(self.cache_dir, exist_ok=True)

        # Add model selection dropdowns
        model_layout = QHBoxLayout()
        self.retrieval_model_combo = QComboBox()
        self.validation_model_combo = QComboBox()
        models = ["llama-3.1-sonar-huge-128k-online", "llama-3.1-sonar-small-128k-online"]
        self.retrieval_model_combo.addItems(models)
        self.validation_model_combo.addItems(models)
        model_layout.addWidget(QLabel("Retrieval Model:"))
        model_layout.addWidget(self.retrieval_model_combo)
        model_layout.addWidget(QLabel("Validation Model:"))
        model_layout.addWidget(self.validation_model_combo)
        self.layout.addLayout(model_layout)

        self.threadpool = QThreadPool()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_operation)
        self.cancel_button.hide()
        self.layout.addWidget(self.cancel_button)

        # Add new right-hand side layout for Image URL and Links
        right_side_layout = QVBoxLayout()
        
        # Image URL input
        image_url_layout = QHBoxLayout()
        image_url_label = QLabel("Image URL:")
        self.image_url_input = QLineEdit()
        image_url_layout.addWidget(image_url_label)
        image_url_layout.addWidget(self.image_url_input)
        right_side_layout.addLayout(image_url_layout)
        
        # Links management
        links_label = QLabel("Product Links:")
        right_side_layout.addWidget(links_label)
        
        self.links_layout = QVBoxLayout()
        self.links = []  # List to store link widgets
        right_side_layout.addLayout(self.links_layout)
        
        add_link_button = QPushButton("Add Link")
        add_link_button.clicked.connect(lambda: self.add_link())
        right_side_layout.addWidget(add_link_button)
        
        bottom_layout.addLayout(right_side_layout, 1)

    def update_compatibility_checkboxes(self):
        try:
            category = self.category_combo.currentText()
            if category in self.compatibility_data:
                compatibility_widget = self.findChild(QScrollArea).widget()
                compatibility_layout = compatibility_widget.layout()

                # Clear existing layout
                while compatibility_layout.count():
                    child = compatibility_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

                self.compatibility_checkboxes = {}

                for tag, options in self.compatibility_data[category].items():
                    group_widget = QWidget()
                    group_layout = QVBoxLayout(group_widget)
                    group_layout.addWidget(QLabel(tag))
                    for option in options:
                        checkbox = QCheckBox(option)
                        group_layout.addWidget(checkbox)
                        self.compatibility_checkboxes.setdefault(tag, []).append(checkbox)
                    compatibility_layout.addWidget(group_widget)

        except Exception as e:
            print(f"Error updating compatibility checkboxes: {str(e)}")
            QMessageBox.warning(self, "Warning", f"Error updating compatibility checkboxes: {str(e)}")

    def get_product_info(self, category, product_name):
        # cache_file = os.path.join(self.cache_dir, f"{category}_{product_name.replace(' ', '_')}.pkl")
        
        # if os.path.exists(cache_file):
        #     with open(cache_file, 'rb') as f:
        #         return pickle.load(f)

        with open('data/src/prompts.md', 'r') as file:
            prompt_template = file.read()

        compatibility_tags = self.compatibility_data[category]
        
        # Create the compatibility tags string
        compatibility_tags_str = "\n".join([f"   - {tag}: {options}" for tag, options in compatibility_tags.items()])
        
        # Create the compatibility JSON structure
        compatibility_json_str = "\n".join([f'    "{tag}": ["string" or null],' for tag in compatibility_tags.keys()])
        compatibility_json_str = compatibility_json_str.rstrip(',')  # Remove the last comma

        # Replace placeholders in the template
        full_prompt = prompt_template.replace("{CATEGORY}", category)
        full_prompt = full_prompt.replace("{COMPATIBILITY_TAGS}", compatibility_tags_str)
        full_prompt = full_prompt.replace("{COMPATIBILITY_JSON}", compatibility_json_str)

        full_prompt += f"\n\nProduct title: {product_name}\n\nPlease provide the response in valid JSON format."
        
        response = query_perplexity(full_prompt, model=self.retrieval_model_combo.currentText())
        
        try:
            result = json.loads(response)
            # with open(cache_file, 'wb') as f:
            #     pickle.dump(result, f)
            return result
        except json.JSONDecodeError:
            return response  # Return the raw response if not valid JSON

    def get_info(self):
        category = self.category_combo.currentText()
        product_name = self.product_input.text()

        if not category or not product_name:
            QMessageBox.critical(self, "Error", "Please enter both category and product name")
            return

        self.progress_bar.show()
        self.progress_bar.setValue(0)

        worker = Worker(self.process_product_info, category, product_name)
        worker.signals.result.connect(self.handle_result)
        worker.signals.finished.connect(self.handle_finished)
        worker.signals.error.connect(self.handle_error)

        self.threadpool.start(worker)

        self.get_info_button.setEnabled(False)
        self.cancel_button.show()

    def process_product_info(self, category, product_name):
        product_info = self.get_product_info(category, product_name)
        if isinstance(product_info, dict):
            validated_info = self.validate_product_info(category, product_info)
            return validated_info
        else:
            return product_info

    def handle_result(self, result):
        if isinstance(result, dict):
            self.json_text.setPlainText(json.dumps(result, indent=2))
            self.update_compatibility_checkboxes()
            self.refresh_compatibility()
        else:
            error_message = f"Unexpected response from Perplexity API:\n\n{result}"
            self.json_text.setPlainText(error_message)
            print(error_message)
            QMessageBox.warning(self, "Warning", "Received unexpected response from Perplexity API. Check the JSON output for details.")

    def handle_finished(self):
        self.progress_bar.setValue(100)
        QTimer.singleShot(1000, self.progress_bar.hide)
        self.get_info_button.setEnabled(True)
        self.cancel_button.hide()

    def handle_error(self, error):
        QMessageBox.critical(self, "Error", f"An error occurred: {error}")
        self.progress_bar.hide()

    def validate_product_info(self, category, product_info):
        validation_prompt = f"""
        You are a specialized FPV drone part data validator. Please review and correct the following JSON data for a {category} product:

        {json.dumps(product_info, indent=2)}

        Please focus on the following tasks:
        1. Ensure all compatibility tags are correct and relevant for the {category} category. 
        2. Verify that the links are valid, if there are only a few links, check them manually or add more links that are accurate. 
        3. Check that the prices are precise and accurate. They should be in the correct format (float).
        4. Make sure the specifications are relevant and accurate for a {category} product. Only include specifications that are not already mentioned in the compatibility tags.

        If you find any issues or have any corrections, please provide the full corrected JSON data. If everything is correct, simply return the original JSON data.

        Your response should be a valid JSON object and nothing else.
        """

        validated_response = query_perplexity(validation_prompt, model=self.validation_model_combo.currentText())
        
        try:
            validated_info = json.loads(validated_response)
            return validated_info
        except json.JSONDecodeError:
            print(f"Error decoding validated JSON: {validated_response}")
            return product_info  # Return original data if validation fails

    def refresh_compatibility(self):
        try:
            data = json.loads(self.json_text.toPlainText())
            
            # Update compatibility checkboxes
            compatibility_tags = data.get("compatibilityTags", {})
            for tag, checkboxes in self.compatibility_checkboxes.items():
                selected_options = compatibility_tags.get(tag, [])
                if selected_options is None:
                    selected_options = []
                for checkbox in checkboxes:
                    checkbox.setChecked(checkbox.text() in selected_options)
            
            # Update image URL
            self.image_url_input.setText(data.get("image", ""))
            
            # Update product links
            links_data = data.get("links", {})
            
            # Clear existing links
            while self.links:
                self.remove_link(self.links[0])
            
            # Add new links from JSON data
            for name, link_info in links_data.items():
                if isinstance(link_info, dict):
                    url = link_info.get("url", "")
                else:
                    url = link_info  # In case it's a direct URL string
                self.add_link(name, url)
                
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Warning", "Invalid JSON data. Unable to refresh compatibility.")
        except Exception as e:
            print(f"Error refreshing compatibility: {str(e)}")
            QMessageBox.warning(self, "Warning", f"Error refreshing compatibility: {str(e)}")

    def send_to_db(self):
        try:
            data = json.loads(self.json_text.toPlainText())
            
            # Update compatibilityTags based on checkboxes
            compatibility_tags = {}
            for tag, checkboxes in self.compatibility_checkboxes.items():
                selected_options = [cb.text() for cb in checkboxes if cb.isChecked()]
                if selected_options:
                    compatibility_tags[tag] = selected_options
            
            data["compatibilityTags"] = compatibility_tags
            
            # Add Image URL
            data["image"] = self.image_url_input.text() if self.image_url_input.text() else None
            
            # Add Links
            links_data = {}
            for link_widget in self.links:
                name = link_widget.layout().itemAt(0).widget().text()
                url = link_widget.layout().itemAt(1).widget().text()
                if name and url:
                    links_data[name] = {"url": url, "price": None}  # You might want to add a field for price input
            data["links"] = links_data if links_data else None
            
            category = self.category_combo.currentText()
            inserted_id = send_to_mongodb(data, category)
            QMessageBox.information(self, "Success", f"Data sent to MongoDB. Category: {category}, Inserted ID: {inserted_id}")
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Invalid JSON data")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to send data to MongoDB: {str(e)}")

    def add_new_entry(self):
        category = self.category_combo.currentText()
        if category not in self.compatibility_data:
            QMessageBox.warning(self, "Warning", f"No compatibility data for category: {category}")
            return

        dialog = NewEntryDialog(self.compatibility_data[category].keys(), self)
        if dialog.exec():
            subcategory, new_entry = dialog.get_values()
            if subcategory and new_entry:
                if new_entry not in self.compatibility_data[category][subcategory]:
                    self.compatibility_data[category][subcategory].append(new_entry)
                    self.update_compatibility_checkboxes()
                    QMessageBox.information(self, "Success", f"Added '{new_entry}' to '{subcategory}' in '{category}'")
                else:
                    QMessageBox.warning(self, "Warning", f"Entry '{new_entry}' already exists in '{subcategory}'")
            else:
                QMessageBox.warning(self, "Warning", "Both subcategory and new entry must be provided")

    def cancel_operation(self):
        self.threadpool.clear()
        self.handle_finished()

    def add_link(self, name=None, url=None):
        link_widget = QWidget()
        link_layout = QHBoxLayout()
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("Link Name")
        if isinstance(name, str):
            name_input.setText(name)
        
        url_input = QLineEdit()
        url_input.setPlaceholderText("URL")
        if isinstance(url, str):
            url_input.setText(url)
        
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self.remove_link(link_widget))
        
        link_layout.addWidget(name_input)
        link_layout.addWidget(url_input)
        link_layout.addWidget(remove_button)
        link_widget.setLayout(link_layout)
        
        self.links_layout.addWidget(link_widget)
        self.links.append(link_widget)
    
    def remove_link(self, link_widget):
        self.links_layout.removeWidget(link_widget)
        link_widget.deleteLater()
        self.links.remove(link_widget)

class NewEntryDialog(QDialog):
    def __init__(self, subcategories, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Compatibility Entry")
        self.setGeometry(300, 300, 350, 150)

        layout = QVBoxLayout(self)

        self.subcategory_combo = QComboBox()
        self.subcategory_combo.addItems(subcategories)
        layout.addWidget(QLabel("Subcategory:"))
        layout.addWidget(self.subcategory_combo)

        self.new_entry_input = QLineEdit()
        layout.addWidget(QLabel("New Entry:"))
        layout.addWidget(self.new_entry_input)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_values(self):
        return self.subcategory_combo.currentText(), self.new_entry_input.text()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPV Database Populator")
        self.setGeometry(100, 100, 1200, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)

        # Add initial tab
        self.add_new_tab()

        # Add New Tab button
        self.add_tab_button = QPushButton("Add New Tab")
        self.add_tab_button.clicked.connect(self.add_new_tab)
        self.layout.addWidget(self.add_tab_button)

        # Send to MongoDB button
        self.send_to_db_button = QPushButton("Send to MongoDB")
        self.send_to_db_button.clicked.connect(self.send_active_tab_to_db)
        self.layout.addWidget(self.send_to_db_button)

    def add_new_tab(self):
        new_tab = ProductTab(self)
        tab_index = self.tab_widget.addTab(new_tab, f"Product {self.tab_widget.count() + 1}")
        self.tab_widget.setCurrentIndex(tab_index)

    def send_active_tab_to_db(self):
        active_tab = self.tab_widget.currentWidget()
        if active_tab:
            active_tab.send_to_db()
        else:
            QMessageBox.warning(self, "Warning", "No active tab to send to MongoDB")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())