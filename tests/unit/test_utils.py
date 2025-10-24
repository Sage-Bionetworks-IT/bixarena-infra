import json
import pytest
import tempfile
import yaml
from pathlib import Path

from src.utils import load_context_config


class TestLoadContextConfig:
    """Test suite for the load_context_config function."""

    def test_invalid_environment_raises_value_error(self):
        """Test that invalid environment names raise ValueError."""
        invalid_envs = ["invalid", "test", "production", "development", ""]

        for env in invalid_envs:
            with pytest.raises(ValueError, match=f"Invalid environment '{env}'"):
                load_context_config(env)

    def test_valid_environments(self):
        """Test that valid environment names are accepted."""
        valid_envs = ["dev", "stage", "prod"]

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a basic config file for each valid environment
            for env in valid_envs:
                config_file = Path(temp_dir) / f"{env}.yaml"
                with open(config_file, "w") as f:
                    yaml.dump({"test": "value"}, f)

                # Should not raise an exception
                result = load_context_config(env, temp_dir)
                assert result == {"test": "value"}

    def test_no_config_file_raises_file_not_found_error(self):
        """Test that missing config files raise FileNotFoundError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(
                FileNotFoundError, match="No config file found for environment 'dev'"
            ):
                load_context_config("dev", temp_dir)

    def test_multiple_config_files_raises_value_error(self):
        """Test that multiple config files for same environment raise ValueError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple config files for the same environment
            yaml_file = Path(temp_dir) / "dev.yaml"
            json_file = Path(temp_dir) / "dev.json"

            with open(yaml_file, "w") as f:
                yaml.dump({"test": "yaml"}, f)

            with open(json_file, "w") as f:
                json.dump({"test": "json"}, f)

            with pytest.raises(
                ValueError, match="Multiple config files found for environment 'dev'"
            ):
                load_context_config("dev", temp_dir)

    def test_load_yaml_config(self):
        """Test loading YAML configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "dev.yaml"
            config_data = {
                "VPC_CIDR": "10.0.0.0/16",
                "FQDN": "example.com",
                "TAGS": {"Environment": "dev"},
            }

            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            result = load_context_config("dev", temp_dir)
            assert result == config_data

    def test_load_yml_config(self):
        """Test loading .yml configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "dev.yml"
            config_data = {"VPC_CIDR": "10.0.0.0/16", "FQDN": "example.com"}

            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            result = load_context_config("dev", temp_dir)
            assert result == config_data

    def test_load_json_config(self):
        """Test loading JSON configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "dev.json"
            config_data = {
                "VPC_CIDR": "10.0.0.0/16",
                "FQDN": "example.com",
                "TAGS": {"Environment": "dev"},
            }

            with open(config_file, "w") as f:
                json.dump(config_data, f)

            result = load_context_config("dev", temp_dir)
            assert result == config_data

    def test_base_config_merging(self):
        """Test that base.yaml is properly merged with environment config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create base config
            base_file = Path(temp_dir) / "base.yaml"
            base_config = {
                "VPC_CIDR": "10.0.0.0/16",
                "COMMON_SETTING": "base_value",
                "SHARED_SETTING": "from_base",
            }
            with open(base_file, "w") as f:
                yaml.dump(base_config, f)

            # Create environment config
            env_file = Path(temp_dir) / "dev.yaml"
            env_config = {
                "FQDN": "dev.example.com",
                "SHARED_SETTING": "from_env",  # This should override base
                "ENV_SPECIFIC": "dev_value",
            }
            with open(env_file, "w") as f:
                yaml.dump(env_config, f)

            result = load_context_config("dev", temp_dir)

            expected = {
                "VPC_CIDR": "10.0.0.0/16",  # from base
                "COMMON_SETTING": "base_value",  # from base
                "SHARED_SETTING": "from_env",  # env overrides base
                "FQDN": "dev.example.com",  # from env
                "ENV_SPECIFIC": "dev_value",  # from env
            }

            assert result == expected

    def test_no_base_config(self):
        """Test loading config when base.yaml doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / "dev.yaml"
            env_config = {"FQDN": "dev.example.com"}

            with open(env_file, "w") as f:
                yaml.dump(env_config, f)

            result = load_context_config("dev", temp_dir)
            assert result == env_config

    def test_empty_base_config(self):
        """Test handling of empty base config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty base config
            base_file = Path(temp_dir) / "base.yaml"
            with open(base_file, "w") as f:
                f.write("")  # Empty file

            # Create environment config
            env_file = Path(temp_dir) / "dev.yaml"
            env_config = {"FQDN": "dev.example.com"}
            with open(env_file, "w") as f:
                yaml.dump(env_config, f)

            result = load_context_config("dev", temp_dir)
            assert result == env_config

    def test_empty_env_config(self):
        """Test handling of empty environment config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create base config
            base_file = Path(temp_dir) / "base.yaml"
            base_config = {"VPC_CIDR": "10.0.0.0/16"}
            with open(base_file, "w") as f:
                yaml.dump(base_config, f)

            # Create empty environment config
            env_file = Path(temp_dir) / "dev.yaml"
            with open(env_file, "w") as f:
                f.write("")  # Empty file

            result = load_context_config("dev", temp_dir)
            assert result == base_config

    def test_custom_config_dir(self):
        """Test using a custom config directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_dir = Path(temp_dir) / "custom_config"
            custom_dir.mkdir()

            config_file = custom_dir / "dev.yaml"
            config_data = {"FQDN": "custom.example.com"}

            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            result = load_context_config("dev", str(custom_dir))
            assert result == config_data

    def test_yaml_precedence_over_yml(self):
        """Test that when both .yaml and .yml exist, an error is raised."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # This test ensures our error handling works - we should get an error
            # when both .yaml and .yml exist
            yaml_file = Path(temp_dir) / "dev.yaml"
            yml_file = Path(temp_dir) / "dev.yml"

            with open(yaml_file, "w") as f:
                yaml.dump({"source": "yaml"}, f)

            with open(yml_file, "w") as f:
                yaml.dump({"source": "yml"}, f)

            with pytest.raises(ValueError, match="Multiple config files found"):
                load_context_config("dev", temp_dir)

    def test_all_environments_work(self):
        """Test that all valid environments work correctly."""
        environments = ["dev", "stage", "prod"]

        with tempfile.TemporaryDirectory() as temp_dir:
            for env in environments:
                config_file = Path(temp_dir) / f"{env}.yaml"
                config_data = {
                    "FQDN": f"{env}.example.com",
                    "VPC_CIDR": "10.0.0.0/16",
                    "TAGS": {"Environment": env},
                }

                with open(config_file, "w") as f:
                    yaml.dump(config_data, f)

                result = load_context_config(env, temp_dir)
                assert result["FQDN"] == f"{env}.example.com"
                assert result["TAGS"]["Environment"] == env

    def test_invalid_yaml_content(self):
        """Test handling of invalid YAML content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "dev.yaml"
            # Create invalid YAML content
            with open(config_file, "w") as f:
                f.write("invalid: yaml: content: [unclosed")

            with pytest.raises(yaml.YAMLError):
                load_context_config("dev", temp_dir)

    def test_invalid_json_content(self):
        """Test handling of invalid JSON content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "dev.json"
            # Create invalid JSON content
            with open(config_file, "w") as f:
                f.write('{"invalid": json content}')

            with pytest.raises(json.JSONDecodeError):
                load_context_config("dev", temp_dir)
