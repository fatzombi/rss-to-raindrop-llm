terraform {
  backend "s3" {
    bucket = "rss-to-raindrop-tfstate"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}
