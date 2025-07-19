"""Tests for flag types and data structures."""

import unittest
from flags.flag import Details, FeatureFlag


class TestDetails(unittest.TestCase):
    """Test the Details dataclass."""
    
    def test_details_creation(self):
        """Test creating a Details instance."""
        details = Details(name="test-flag", id="test-id")
        self.assertEqual(details.name, "test-flag")
        self.assertEqual(details.id, "test-id")


class TestFeatureFlag(unittest.TestCase):
    """Test the FeatureFlag dataclass."""
    
    def test_feature_flag_creation(self):
        """Test creating a FeatureFlag instance."""
        details = Details(name="test-flag", id="test-id")
        flag = FeatureFlag(enabled=True, details=details)
        
        self.assertTrue(flag.enabled)
        self.assertEqual(flag.details.name, "test-flag")
        self.assertEqual(flag.details.id, "test-id")
    
    def test_from_dict(self):
        """Test creating a FeatureFlag from a dictionary."""
        data = {
            "enabled": True,
            "details": {
                "name": "test-flag",
                "id": "test-id"
            }
        }
        
        flag = FeatureFlag.from_dict(data)
        
        self.assertTrue(flag.enabled)
        self.assertEqual(flag.details.name, "test-flag")
        self.assertEqual(flag.details.id, "test-id")
    
    def test_from_dict_missing_fields(self):
        """Test creating a FeatureFlag from incomplete data."""
        data = {"enabled": True}
        
        flag = FeatureFlag.from_dict(data)
        
        self.assertTrue(flag.enabled)
        self.assertEqual(flag.details.name, "")
        self.assertEqual(flag.details.id, "")
    
    def test_to_dict(self):
        """Test converting a FeatureFlag to a dictionary."""
        details = Details(name="test-flag", id="test-id")
        flag = FeatureFlag(enabled=True, details=details)
        
        data = flag.to_dict()
        
        expected = {
            "enabled": True,
            "details": {
                "name": "test-flag",
                "id": "test-id"
            }
        }
        self.assertEqual(data, expected)


if __name__ == "__main__":
    unittest.main()