variable "region" {
  type    = string
  default = "ap-northeast-1"
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Subnets for ECS tasks"
  type        = list(string)
}

variable "alb_subnet_ids" {
  description = "Subnets for ALB (usually public)"
  type        = list(string)
}

variable "assign_public_ip" {
  type    = bool
  default = true
}

variable "name_prefix" {
  type    = string
  default = "test-otel-sidecar"
}

variable "permission_boundary_arn" {
  description = "IAM Permission Boundary ARN"
  type        = string
}
