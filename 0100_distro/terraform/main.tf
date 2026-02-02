terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_region" "current" {}

locals {
  prefix = var.name_prefix
}


# =============================
# ECS Cluster
# =============================
resource "aws_ecs_cluster" "this" {
  name = "${local.prefix}-cluster"
}

# 1. タスクロールを新設 (コンテナがAWSサービスと通信するため)
resource "aws_iam_role" "ecs_task_role" {
  name = "${local.prefix}-ecs-task-role"
  permissions_boundary = var.permission_boundary_arn
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

# 2. OTelに必要な権限をタスクロールに付与
resource "aws_iam_role_policy_attachment" "task_role_otel" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# X-Rayへの書き込み権限を追加
resource "aws_iam_role_policy_attachment" "task_role_xray" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# =============================
# IAM Role (Task Execution)
# =============================
resource "aws_iam_role" "ecs_task_execution" {
  name                 = "${local.prefix}-ecs-task-execution-role"
  permissions_boundary = var.permission_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_extra_policy" {
  name = "${local.prefix}-ecs-extra-policy"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "s3:GetObject",
          "s3:GetBucketLocation",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================
# Security Groups
# =============================

# ALB
resource "aws_security_group" "alb" {
  name   = "${local.prefix}-alb-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ECS
resource "aws_security_group" "ecs" {
  name   = "${local.prefix}-ecs-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# =============================
# ALB
# =============================
resource "aws_lb" "this" {
  name               = "${local.prefix}-alb"
  load_balancer_type = "application"
  subnets            = var.alb_subnet_ids
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "this" {
  name        = "${local.prefix}-tg"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path = "/"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }
}

resource "aws_ecr_repository" "this" {
  name                 = "${local.prefix}-app"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # 検証用。本番では注意

  image_scanning_configuration {
    scan_on_push = true
  }
}

# =============================
# Task Definition
# =============================
resource "aws_ecs_task_definition" "this" {
  family                   = "${local.prefix}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.ecs_task_role.arn # ここを追加！

  container_definitions = jsonencode([
    # =====================
    # Application (nginx)
    # =====================
    {
      name      = "${local.prefix}-flask"
      image     = aws_ecr_repository.app.repository_url # ECRのURLを参照
      essential = true

      portMappings = [{
        containerPort = 80
        protocol      = "tcp"
      }]

      environment = [
        { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://localhost:4317" },
        { name = "OTEL_RESOURCE_ATTRIBUTES",    value = "service.name=${local.prefix}-flask" },
        { name = "OTEL_METRICS_EXPORTER",       value = "none" }
      ]
    },

    # =====================
    # OpenTelemetry Collector (sidecar)
    # =====================
    {
      name      = "aws-otel-collector"
      image     = "public.ecr.aws/aws-observability/aws-otel-collector:v0.47.0"
      essential = true,
      environment = [
        {
            name = "AWS_OTEL_ECS_ENABLE_CONTAINER_INSIGHTS"
            value = "true"
        }
      ]
      command   = ["--config=/etc/otel-config.yaml"]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-create-group" = "True"
          "awslogs-group"         = "/ecs/example-task-definition"
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "nginx"
        }
      }
    }
  ])
}


# =============================
# ECS Service (ALB連携)
# =============================
resource "aws_ecs_service" "this" {
  name            = "${local.prefix}-service"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = var.assign_public_ip
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.this.arn
    container_name   = "${local.prefix}-nginx"
    container_port   = 80
  }

  depends_on = [aws_lb_listener.http]
}
