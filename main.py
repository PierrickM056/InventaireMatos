import sys
import os
import qrcode
import cv2
from pyzbar.pyzbar import decode, ZBarSymbol
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QDialog, QFormLayout, QLineEdit, QComboBox, 
                             QFileDialog, QMessageBox, QInputDialog, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from database import Database

# Imports pour le PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

# --- LOGIQUE DE GESTION DES FICHIERS ---
class LogicManager:
    @staticmethod
    def setup_folders():
        for path in ["data/qrcodes", "data/factures"]:
            os.makedirs(path, exist_ok=True)

    @staticmethod
    def generate_qr(item_id, sn):
        path = f"data/qrcodes/QR_{item_id}.png"
        img = qrcode.make(f"PROSTOCK-ID:{item_id}-SN:{sn}")
        img.save(path)
        return path

# --- DIALOGUE D'AJOUT DE RÉPARATION ---
class AddRepairDialog(QDialog):
    def __init__(self, item_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Maintenance : {item_name}")
        self.setFixedWidth(400)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.date = QLineEdit()
        import datetime
        self.date.setText(datetime.date.today().strftime("%Y-%m-%d"))
        self.desc = QLineEdit()
        self.cout = QLineEdit()
        self.prestataire = QLineEdit()
        
        form.addRow("Date (AAAA-MM-JJ) :", self.date)
        form.addRow("Description panne :", self.desc)
        form.addRow("Coût (€) :", self.cout)
        form.addRow("Réparateur :", self.prestataire)

        layout.addLayout(form)

        self.btn_save = QPushButton("Enregistrer la réparation")
        self.btn_save.setObjectName("ActionBtn")
        self.btn_save.clicked.connect(self.accept)
        layout.addWidget(self.btn_save)

# --- DIALOGUE DE SÉLECTION D'ITEMS POUR KIT ---
class SelectItemsDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner les objets du kit")
        self.setFixedSize(400, 500)
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for item_id, nom, marque in items:
            list_item = QListWidgetItem(f"[{item_id}] {marque} - {nom}")
            list_item.setData(Qt.ItemDataRole.UserRole, item_id)
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.addItem(list_item)
        
        layout.addWidget(QLabel("Cochez les éléments à inclure :"))
        layout.addWidget(self.list_widget)

        self.btn_confirm = QPushButton("Valider la composition")
        self.btn_confirm.setObjectName("ActionBtn")
        self.btn_confirm.clicked.connect(self.accept)
        layout.addWidget(self.btn_confirm)

    def get_selected_ids(self):
        selected_ids = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_ids.append(item.data(Qt.ItemDataRole.UserRole))
        return selected_ids

# --- MODULE SCANNER WEBCAM ---
class ScannerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scanner QR Code")
        self.setFixedSize(640, 520)
        self.layout = QVBoxLayout(self)
        
        self.video_label = QLabel("Initialisation caméra...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.video_label)
        
        self.result_data = None
        self.cap = cv2.VideoCapture(0)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            for barcode in decode(frame, symbols=[ZBarSymbol.QRCODE]):
                self.result_data = barcode.data.decode('utf-8')
                self.accept() 
            
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(qt_image).scaled(600, 480, Qt.AspectRatioMode.KeepAspectRatio))

    def closeEvent(self, event):
        self.cap.release()
        super().closeEvent(event)

# --- FENÊTRE DE SAISIE (DIALOGUE) ---
class AddDeviceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter un nouvel équipement")
        self.setFixedWidth(450)
        self.facture_path = ""
        
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.nom = QLineEdit()
        self.marque = QLineEdit()
        self.modele = QLineEdit()
        self.sn = QLineEdit()
        self.prix = QLineEdit()
        self.cat = QComboBox()
        self.cat.addItems(["Photo", "Vidéo", "Son", "Lumière", "Accessoires"])
        
        form.addRow("Nom de l'objet :", self.nom)
        form.addRow("Marque :", self.marque)
        form.addRow("Modèle :", self.modele)
        form.addRow("N° de Série :", self.sn)
        form.addRow("Prix d'achat (€) :", self.prix)
        form.addRow("Catégorie :", self.cat)

        self.btn_file = QPushButton("📁 Joindre la facture")
        self.btn_file.clicked.connect(self.select_file)
        form.addRow("Document :", self.btn_file)

        layout.addLayout(form)

        self.btn_save = QPushButton("Enregistrer dans l'inventaire")
        self.btn_save.setObjectName("ActionBtn")
        self.btn_save.clicked.connect(self.accept)
        layout.addWidget(self.btn_save)

    def select_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Sélectionner la facture", "", "Images/PDF (*.jpg *.png *.pdf)")
        if file:
            self.facture_path = file
            self.btn_file.setText("✅ Facture prête")

# --- FENÊTRE PRINCIPALE ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Studio Inventory Manager v1.0")
        self.resize(1200, 800)

        self.db = Database()
        self.load_stylesheet()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QHBoxLayout(main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- SIDEBAR ---
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        
        logo = QLabel("PRO-STOCK")
        logo.setObjectName("TitleLabel")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo)

        self.btn_inv = QPushButton("📦 Inventaire")
        self.btn_kits = QPushButton("🧰 Kits")
        self.btn_check = QPushButton("🔄 Check In/Out")
        self.btn_maint = QPushButton("🛠 Maintenance")
        
        for btn in [self.btn_inv, self.btn_kits, self.btn_check, self.btn_maint]:
            sidebar_layout.addWidget(btn)
        
        sidebar_layout.addStretch()
        self.btn_settings = QPushButton("⚙ Paramètres")
        sidebar_layout.addWidget(self.btn_settings)

        # --- CONTENU ---
        self.content_area = QStackedWidget()
        self.content_area.setObjectName("MainContent")
        
        self.page_inv = self.create_inventory_page()
        self.page_kits = self.create_kits_page()
        self.page_check = self.create_check_page()
        self.page_maint = self.create_maintenance_page()
        
        self.content_area.addWidget(self.page_inv)
        self.content_area.addWidget(self.page_kits)
        self.content_area.addWidget(self.page_check)
        self.content_area.addWidget(self.page_maint)

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.content_area)

        self.btn_inv.clicked.connect(lambda: self.content_area.setCurrentIndex(0))
        self.btn_kits.clicked.connect(lambda: self.content_area.setCurrentIndex(1))
        self.btn_check.clicked.connect(lambda: self.content_area.setCurrentIndex(2))
        self.btn_maint.clicked.connect(lambda: self.content_area.setCurrentIndex(3))

        self.load_data()
        self.load_kits_data()
        self.load_maintenance_data()
        self.load_check_data()

    def load_stylesheet(self):
        if os.path.exists("styles.qss"):
            with open("styles.qss", "r") as f:
                self.setStyleSheet(f.read())

    def create_inventory_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)

        header = QHBoxLayout()
        title = QLabel("Inventaire Global")
        title.setObjectName("TitleLabel")
        
        self.btn_repair = QPushButton("🛠️ Réparer")
        self.btn_repair.setFixedWidth(120)
        self.btn_repair.clicked.connect(self.open_repair_dialog)

        self.btn_print = QPushButton("🖨️ Imprimer Étiquettes")
        self.btn_print.setFixedWidth(180)
        self.btn_print.clicked.connect(self.export_qr_sheet)

        self.btn_scan = QPushButton("📷 Scanner QR")
        self.btn_scan.setObjectName("ActionBtn")
        self.btn_scan.setFixedWidth(150)
        self.btn_scan.clicked.connect(self.open_scanner)

        self.btn_add = QPushButton("+ Ajouter Matériel")
        self.btn_add.setObjectName("ActionBtn")
        self.btn_add.setFixedWidth(200)
        self.btn_add.clicked.connect(self.open_add_dialog)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.btn_repair)
        header.addWidget(self.btn_print)
        header.addWidget(self.btn_scan)
        header.addWidget(self.btn_add)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Nom", "Marque", "S/N", "Statut"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        return page

    def create_check_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)

        header = QHBoxLayout()
        title = QLabel("Matériel en circulation (Check Out)")
        title.setObjectName("TitleLabel")
        
        btn_quick_scan = QPushButton("📷 Scanner pour Retour")
        btn_quick_scan.setObjectName("ActionBtn")
        btn_quick_scan.clicked.connect(self.open_scanner)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(btn_quick_scan)
        layout.addLayout(header)

        self.check_table = QTableWidget()
        self.check_table.setColumnCount(4)
        self.check_table.setHorizontalHeaderLabels(["ID", "Nom", "Marque", "Statut"])
        self.check_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.check_table)

        btn_return_all = QPushButton("Remettre tout en stock")
        btn_return_all.clicked.connect(self.return_all_selected)
        layout.addWidget(btn_return_all)

        return page

    def load_check_data(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, nom, marque, statut FROM equipement WHERE statut = 'Sorti'")
        rows = cursor.fetchall()
        self.check_table.setRowCount(0)
        for row_idx, row_data in enumerate(rows):
            self.check_table.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                self.check_table.setItem(row_idx, col_idx, QTableWidgetItem(str(data)))

    def return_all_selected(self):
        cursor = self.db.conn.cursor()
        cursor.execute("UPDATE equipement SET statut = 'En stock' WHERE statut = 'Sorti'")
        self.db.conn.commit()
        self.load_data()
        self.load_check_data()
        QMessageBox.information(self, "Check In", "Tout le matériel a été remis en stock.")

    def create_maintenance_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Historique de Maintenance")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        self.maint_table = QTableWidget()
        self.maint_table.setColumnCount(5)
        self.maint_table.setHorizontalHeaderLabels(["Date", "Objet", "Description", "Coût (€)", "Réparateur"])
        self.maint_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.maint_table)
        
        return page

    def load_maintenance_data(self):
        cursor = self.db.conn.cursor()
        query = """
            SELECT r.date_reparation, e.nom, r.description, r.cout, r.prestataire 
            FROM reparations r
            JOIN equipement e ON r.id_equipement = e.id
            ORDER BY r.date_reparation DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        self.maint_table.setRowCount(0)
        for row_idx, row_data in enumerate(rows):
            self.maint_table.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                self.maint_table.setItem(row_idx, col_idx, QTableWidgetItem(str(data)))

    def open_repair_dialog(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un objet.")
            return
        
        row = selected_rows[0].row()
        item_id = self.table.item(row, 0).text()
        item_name = self.table.item(row, 1).text()
        
        dialog = AddRepairDialog(item_name, self)
        if dialog.exec():
            cursor = self.db.conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO reparations (id_equipement, date_reparation, description, cout, prestataire)
                    VALUES (?, ?, ?, ?, ?)
                """, (item_id, dialog.date.text(), dialog.desc.text(), dialog.cout.text(), dialog.prestataire.text()))
                self.db.conn.commit()
                self.load_maintenance_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur : {e}")

    def export_qr_sheet(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            reply = QMessageBox.question(self, "Impression", "Aucune ligne sélectionnée. Imprimer tout ?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                rows_to_print = range(self.table.rowCount())
            else: return
        else:
            rows_to_print = [r.row() for r in selected_rows]

        file_path, _ = QFileDialog.getSaveFileName(self, "Enregistrer", "planche.pdf", "PDF (*.pdf)")
        if not file_path: return

        c = canvas.Canvas(file_path, pagesize=A4)
        width, height = A4
        x_start, y_start = 1*cm, height - 4*cm
        count = 0
        for row_idx in rows_to_print:
            item_id = self.table.item(row_idx, 0).text()
            nom, marque = self.table.item(row_idx, 1).text(), self.table.item(row_idx, 2).text()
            qr_file = f"data/qrcodes/QR_{item_id}.png"
            if os.path.exists(qr_file):
                curr_x, curr_y = x_start + ((count % 4) * 5*cm), y_start - ((count // 4) * 5*cm)
                c.drawImage(qr_file, curr_x, curr_y, 3.5*cm, 3.5*cm)
                c.setFont("Helvetica-Bold", 8); c.drawCentredString(curr_x + 1.75*cm, curr_y - 0.3*cm, marque)
                c.setFont("Helvetica", 7); c.drawCentredString(curr_x + 1.75*cm, curr_y - 0.7*cm, nom[:25])
                count += 1
                if count >= 20: c.showPage(); y_start = height - 4*cm; count = 0
        c.save()
        QMessageBox.information(self, "Impression", "PDF généré.")

    def create_kits_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        header = QHBoxLayout()
        title = QLabel("Gestion des Kits")
        title.setObjectName("TitleLabel")
        btn_add_kit = QPushButton("+ Nouveau Kit")
        btn_add_kit.setObjectName("ActionBtn")
        btn_add_kit.setFixedWidth(180)
        btn_add_kit.clicked.connect(self.create_new_kit)
        header.addWidget(title); header.addStretch(); header.addWidget(btn_add_kit)
        layout.addLayout(header)
        self.kits_table = QTableWidget()
        self.kits_table.setColumnCount(4) # Ajout d'une colonne d'action
        self.kits_table.setHorizontalHeaderLabels(["ID", "Nom du Kit", "Nb Objets", "Action"])
        self.kits_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.kits_table)
        return page

    def load_kits_data(self):
        cursor = self.db.conn.cursor()
        query = "SELECT k.id, k.nom_kit, COUNT(ki.id_equipement) FROM kits k LEFT JOIN kit_items ki ON k.id = ki.id_kit GROUP BY k.id"
        cursor.execute(query)
        rows = cursor.fetchall()
        self.kits_table.setRowCount(0)
        for row_idx, row_data in enumerate(rows):
            self.kits_table.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                self.kits_table.setItem(row_idx, col_idx, QTableWidgetItem(str(data)))
            
            # Bouton Action pour le kit
            btn_toggle = QPushButton("Basculer Statut")
            btn_toggle.clicked.connect(lambda ch, kit_id=row_data[0]: self.toggle_kit_status(kit_id))
            self.kits_table.setCellWidget(row_idx, 3, btn_toggle)

    def toggle_kit_status(self, kit_id):
        cursor = self.db.conn.cursor()
        # On récupère le statut du premier objet du kit pour décider de l'action
        cursor.execute("""
            SELECT e.statut FROM equipement e 
            JOIN kit_items ki ON e.id = ki.id_equipement 
            WHERE ki.id_kit = ? LIMIT 1
        """, (kit_id,))
        res = cursor.fetchone()
        if not res: return

        nouveau = "Sorti" if res[0] == "En stock" else "En stock"
        cursor.execute("""
            UPDATE equipement SET statut = ? 
            WHERE id IN (SELECT id_equipement FROM kit_items WHERE id_kit = ?)
        """, (nouveau, kit_id))
        self.db.conn.commit()
        self.load_data()
        self.load_check_data()
        QMessageBox.information(self, "Kits", f"Tout le kit est désormais : {nouveau}")

    def load_data(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, nom, marque, sn, statut FROM equipement")
        rows = cursor.fetchall()
        self.table.setRowCount(0)
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                item = QTableWidgetItem(str(data))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row_idx, col_idx, item)

    def create_new_kit(self):
        nom_kit, ok = QInputDialog.getText(self, "Nouveau Kit", "Nom du Kit :")
        if ok and nom_kit:
            cursor = self.db.conn.cursor()
            try:
                cursor.execute("INSERT INTO kits (nom_kit) VALUES (?)", (nom_kit,))
                kit_id = cursor.lastrowid
                cursor.execute("SELECT id, nom, marque FROM equipement")
                all_items = cursor.fetchall()
                select_dialog = SelectItemsDialog(all_items, self)
                if select_dialog.exec():
                    for item_id in select_dialog.get_selected_ids():
                        cursor.execute("INSERT INTO kit_items (id_kit, id_equipement) VALUES (?, ?)", (kit_id, item_id))
                    self.db.conn.commit(); self.load_kits_data()
                else: self.db.conn.rollback()
            except Exception as e: QMessageBox.warning(self, "Erreur", f"Erreur : {e}")

    def open_add_dialog(self):
        dialog = AddDeviceDialog(self)
        if dialog.exec():
            nom, marque, sn = dialog.nom.text(), dialog.marque.text(), dialog.sn.text()
            if not sn: QMessageBox.warning(self, "Erreur", "S/N obligatoire."); return
            cursor = self.db.conn.cursor()
            try:
                cursor.execute("INSERT INTO equipement (nom, marque, sn, statut) VALUES (?, ?, ?, ?)", (nom, marque, sn, "En stock"))
                item_id = cursor.lastrowid
                qr_path = LogicManager.generate_qr(item_id, sn)
                cursor.execute("UPDATE equipement SET qr_path = ? WHERE id = ?", (qr_path, item_id))
                self.db.conn.commit(); self.load_data()
            except Exception as e: QMessageBox.critical(self, "Erreur", f"Erreur : {e}")

    def open_scanner(self):
        scanner = ScannerDialog(self)
        if scanner.exec() and scanner.result_data:
            try:
                scanned_id = scanner.result_data.split("ID:")[1].split("-")[0]
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT nom, statut FROM equipement WHERE id = ?", (scanned_id,))
                result = cursor.fetchone()
                if result:
                    nom, statut = result
                    nouveau = "Sorti" if statut == "En stock" else "En stock"
                    cursor.execute("UPDATE equipement SET statut = ? WHERE id = ?", (nouveau, scanned_id))
                    self.db.conn.commit()
                    self.load_data()
                    self.load_check_data()
                    QMessageBox.information(self, "Check In/Out", f"{nom} : {nouveau}")
            except: QMessageBox.warning(self, "Erreur", "QR invalide.")

    def create_placeholder_page(self, text):
        page = QWidget(); l = QVBoxLayout(page); lbl = QLabel(text); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); l.addWidget(lbl); return page

if __name__ == "__main__":
    LogicManager.setup_folders()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())