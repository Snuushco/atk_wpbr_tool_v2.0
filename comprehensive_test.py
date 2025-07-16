import os
import sys
import sqlite3
import smtplib
import requests
import json
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta

# Laad environment variables
load_dotenv()

# Configureer logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Test configuratie
BASE_URL = "http://localhost:8000"
TEST_EMAIL = os.getenv('SMTP_USERNAME', 'test@example.com')
TEST_PASSWORD = "TestPassword123!"

class ATKToolTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.current_user = None
        
    def log_test(self, test_name, success, message=""):
        """Log een test resultaat"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = f"{status} {test_name}: {message}"
        print(result)
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message,
            'timestamp': datetime.now()
        })
        return success
    
    def test_environment_setup(self):
        """Test 1: Environment setup en dependencies"""
        print("\n=== Test 1: Environment Setup ===")
        
        # Test environment variables
        required_vars = ['SMTP_SERVER', 'SMTP_USERNAME', 'SMTP_PASSWORD']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.log_test("Environment Variables", False, f"Missing: {', '.join(missing_vars)}")
            return False
        else:
            self.log_test("Environment Variables", True, "All required variables present")
        
        # Test database file
        if os.path.exists('users.db'):
            self.log_test("Database File", True, "users.db exists")
        else:
            self.log_test("Database File", False, "users.db not found")
            return False
        
        # Test uploads directory
        if os.path.exists('uploads'):
            self.log_test("Uploads Directory", True, "uploads directory exists")
        else:
            self.log_test("Uploads Directory", False, "uploads directory not found")
            return False
        
        return True
    
    def test_database_structure(self):
        """Test 2: Database structuur en tabellen"""
        print("\n=== Test 2: Database Structure ===")
        
        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            # Test users table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone():
                self.log_test("Users Table", True, "users table exists")
            else:
                self.log_test("Users Table", False, "users table not found")
                return False
            
            # Test email_tracking table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_tracking'")
            if cursor.fetchone():
                self.log_test("Email Tracking Table", True, "email_tracking table exists")
            else:
                self.log_test("Email Tracking Table", False, "email_tracking table not found")
                return False
            
            # Test table columns
            cursor.execute("PRAGMA table_info(users)")
            user_columns = [row[1] for row in cursor.fetchall()]
            required_user_columns = ['id', 'email', 'hashed_password', 'name']
            
            missing_columns = [col for col in required_user_columns if col not in user_columns]
            if missing_columns:
                self.log_test("Users Table Columns", False, f"Missing columns: {missing_columns}")
                return False
            else:
                self.log_test("Users Table Columns", True, "All required columns present")
            
            conn.close()
            return True
            
        except Exception as e:
            self.log_test("Database Connection", False, str(e))
            return False
    
    def test_email_configuration(self):
        """Test 3: Email configuratie en SMTP verbinding"""
        print("\n=== Test 3: Email Configuration ===")
        
        SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
        SMTP_USERNAME = os.getenv('SMTP_USERNAME')
        SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
        
        # Test SMTP verbinding
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                self.log_test("SMTP Connection", True, f"Connected to {SMTP_SERVER}")
        except Exception as e:
            self.log_test("SMTP Connection", False, str(e))
            return False
        
        # Test email verzending
        try:
            msg = MIMEMultipart()
            msg['From'] = f"ATK-WPBR Tool <{SMTP_USERNAME}>"
            msg['To'] = SMTP_USERNAME
            msg['Subject'] = 'Test Email - ATK-WPBR Tool'
            msg['X-Mailer'] = 'ATK-WPBR Tool v2.0'
            
            body = "Dit is een test email van de ATK-WPBR Tool."
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(SMTP_USERNAME, [SMTP_USERNAME], msg.as_string())
                self.log_test("Email Sending", True, "Test email sent successfully")
        except Exception as e:
            self.log_test("Email Sending", False, str(e))
            return False
        
        return True
    
    def test_web_server(self):
        """Test 4: Web server en routes"""
        print("\n=== Test 4: Web Server ===")
        
        # Test server bereikbaarheid
        try:
            response = self.session.get(f"{BASE_URL}/", timeout=5)
            if response.status_code == 200:
                self.log_test("Server Reachability", True, "Server responds to requests")
            else:
                self.log_test("Server Reachability", False, f"Status code: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.log_test("Server Reachability", False, f"Connection failed: {e}")
            return False
        
        # Test login pagina
        try:
            response = self.session.get(f"{BASE_URL}/login", timeout=5)
            if response.status_code == 200 and "login" in response.text.lower():
                self.log_test("Login Page", True, "Login page accessible")
            else:
                self.log_test("Login Page", False, "Login page not accessible")
                return False
        except Exception as e:
            self.log_test("Login Page", False, str(e))
            return False
        
        # Test register pagina
        try:
            response = self.session.get(f"{BASE_URL}/register", timeout=5)
            if response.status_code == 200:
                self.log_test("Register Page", True, "Register page accessible")
            else:
                self.log_test("Register Page", False, "Register page not accessible")
        except Exception as e:
            self.log_test("Register Page", False, str(e))
        
        return True
    
    def test_user_registration(self):
        """Test 5: Gebruiker registratie"""
        print("\n=== Test 5: User Registration ===")
        
        # Genereer unieke test email
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        test_email = f"test_{timestamp}@atk-wpbr.nl"
        
        # Test registratie
        try:
            registration_data = {
                'name': 'Test User',
                'email': test_email,
                'password': TEST_PASSWORD,
                'vergunningnummer': 'TEST123',
                'terms_accepted': True,
                'privacy_accepted': True
            }
            
            response = self.session.post(
                f"{BASE_URL}/register",
                json=registration_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.log_test("User Registration", True, f"User {test_email} registered successfully")
                    self.current_user = test_email
                else:
                    self.log_test("User Registration", False, result.get('message', 'Unknown error'))
                    return False
            else:
                self.log_test("User Registration", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("User Registration", False, str(e))
            return False
        
        return True
    
    def test_user_login(self):
        """Test 6: Gebruiker login"""
        print("\n=== Test 6: User Login ===")
        
        if not self.current_user:
            self.log_test("User Login", False, "No test user available")
            return False
        
        try:
            login_data = {
                'email': self.current_user,
                'password': TEST_PASSWORD
            }
            
            response = self.session.post(
                f"{BASE_URL}/login",
                json=login_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.log_test("User Login", True, f"User {self.current_user} logged in successfully")
                else:
                    self.log_test("User Login", False, result.get('message', 'Unknown error'))
                    return False
            else:
                self.log_test("User Login", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("User Login", False, str(e))
            return False
        
        return True
    
    def test_form_access(self):
        """Test 7: Formulier toegang"""
        print("\n=== Test 7: Form Access ===")
        
        try:
            response = self.session.get(f"{BASE_URL}/form", timeout=10)
            
            if response.status_code == 200:
                if "form" in response.text.lower() or "aanvraag" in response.text.lower():
                    self.log_test("Form Access", True, "Form page accessible")
                else:
                    self.log_test("Form Access", False, "Form content not found")
                    return False
            else:
                self.log_test("Form Access", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Form Access", False, str(e))
            return False
        
        return True
    
    def test_file_upload(self):
        """Test 8: Bestand upload functionaliteit"""
        print("\n=== Test 8: File Upload ===")
        
        # Maak een test bestand
        test_file_content = "Dit is een test bestand voor upload functionaliteit."
        test_filename = f"test_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        try:
            with open(test_filename, 'w', encoding='utf-8') as f:
                f.write(test_file_content)
            
            # Test upload
            with open(test_filename, 'rb') as f:
                files = {'pasfoto': (test_filename, f, 'text/plain')}
                response = self.session.post(
                    f"{BASE_URL}/uploads",
                    files=files,
                    timeout=30
                )
            
            # Cleanup test file
            if os.path.exists(test_filename):
                os.remove(test_filename)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.log_test("File Upload", True, f"File {test_filename} uploaded successfully")
                else:
                    self.log_test("File Upload", False, result.get('message', 'Unknown error'))
                    return False
            else:
                self.log_test("File Upload", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("File Upload", False, str(e))
            return False
        
        return True
    
    def test_wpbr_data(self):
        """Test 9: WPBR data toegang"""
        print("\n=== Test 9: WPBR Data Access ===")
        
        try:
            response = self.session.get(f"{BASE_URL}/wpbr.json", timeout=10)
            
            if response.status_code == 200:
                try:
                    wpbr_data = response.json()
                    if isinstance(wpbr_data, list) and len(wpbr_data) > 0:
                        self.log_test("WPBR Data", True, f"WPBR data loaded: {len(wpbr_data)} records")
                    else:
                        self.log_test("WPBR Data", False, "WPBR data is empty or invalid format")
                        return False
                except json.JSONDecodeError:
                    self.log_test("WPBR Data", False, "Invalid JSON format")
                    return False
            else:
                self.log_test("WPBR Data", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("WPBR Data", False, str(e))
            return False
        
        return True
    
    def test_email_tracking(self):
        """Test 10: Email tracking functionaliteit"""
        print("\n=== Test 10: Email Tracking ===")
        
        try:
            # Test email tracking pixel route
            test_email_id = "test_email_id_123"
            response = self.session.get(f"{BASE_URL}/email-tracking/{test_email_id}", timeout=10)
            
            if response.status_code == 200:
                self.log_test("Email Tracking Pixel", True, "Tracking pixel route accessible")
            else:
                self.log_test("Email Tracking Pixel", False, f"Status code: {response.status_code}")
                return False
            
            # Test email delivered route
            response = self.session.get(f"{BASE_URL}/email-delivered/{test_email_id}", timeout=10)
            
            if response.status_code == 200:
                self.log_test("Email Delivered Route", True, "Email delivered route accessible")
            else:
                self.log_test("Email Delivered Route", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Email Tracking", False, str(e))
            return False
        
        return True
    
    def test_cleanup(self):
        """Test 11: Cleanup functionaliteit"""
        print("\n=== Test 11: Cleanup ===")
        
        try:
            response = self.session.post(f"{BASE_URL}/cleanup", timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.log_test("Cleanup", True, "Cleanup successful")
                else:
                    self.log_test("Cleanup", False, result.get('message', 'Unknown error'))
            else:
                self.log_test("Cleanup", False, f"Status code: {response.status_code}")
                
        except Exception as e:
            self.log_test("Cleanup", False, str(e))
        
        return True
    
    def generate_test_report(self):
        """Genereer een test rapport"""
        print("\n" + "="*60)
        print("ATK-WPBR TOOL COMPREHENSIVE TEST REPORT")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"\nTest Summary:")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\nFailed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['message']}")
        
        print(f"\nDetailed Results:")
        for result in self.test_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"  {status} {result['test']}")
        
        # Sla rapport op in bestand
        report_filename = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write("ATK-WPBR TOOL COMPREHENSIVE TEST REPORT\n")
            f.write("="*60 + "\n\n")
            f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Tests: {total_tests}\n")
            f.write(f"Passed: {passed_tests}\n")
            f.write(f"Failed: {failed_tests}\n")
            f.write(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%\n\n")
            
            f.write("Detailed Results:\n")
            for result in self.test_results:
                status = "PASS" if result['success'] else "FAIL"
                f.write(f"{status}: {result['test']} - {result['message']}\n")
        
        print(f"\nTest report saved to: {report_filename}")
        
        return passed_tests == total_tests
    
    def run_all_tests(self):
        """Voer alle tests uit"""
        print("Starting ATK-WPBR Tool Comprehensive Tests...")
        print("Make sure the application is running on http://localhost:8000")
        print("="*60)
        
        tests = [
            self.test_environment_setup,
            self.test_database_structure,
            self.test_email_configuration,
            self.test_web_server,
            self.test_user_registration,
            self.test_user_login,
            self.test_form_access,
            self.test_file_upload,
            self.test_wpbr_data,
            self.test_email_tracking,
            self.test_cleanup
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_test(test.__name__, False, f"Test crashed: {str(e)}")
        
        return self.generate_test_report()

def main():
    """Hoofdfunctie voor het uitvoeren van tests"""
    tester = ATKToolTester()
    
    print("ATK-WPBR Tool Comprehensive Test Suite")
    print("This will test all major functionalities of the application.")
    print("\nPrerequisites:")
    print("1. Make sure the Flask application is running (py app.py)")
    print("2. Ensure all environment variables are set")
    print("3. Check that the database is initialized")
    
    input("\nPress Enter to start testing...")
    
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! The ATK-WPBR Tool is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please check the detailed report above.")
    
    return success

if __name__ == "__main__":
    main() 
