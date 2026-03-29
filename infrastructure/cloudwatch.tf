# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "main" {
  name              = "/${var.project_name}/${var.environment}"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-logs"
  }
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/${var.project_name}/backend"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-backend-logs"
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/${var.project_name}/worker"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-worker-logs"
  }
}

# SNS Topic for alarms (optional)
resource "aws_sns_topic" "alarms" {
  count             = var.alarm_email != "" ? 1 : 0
  name              = "${var.project_name}-alarms"
  kms_master_key_id = "alias/aws/sns" # AWS managed key for encryption
}

resource "aws_sns_topic_subscription" "alarms_email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# EC2 CPU Alarm
resource "aws_cloudwatch_metric_alarm" "ec2_cpu" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${var.project_name}-ec2-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "EC2 CPU utilization > 80%"
  alarm_actions       = [aws_sns_topic.alarms[0].arn]

  dimensions = {
    InstanceId = aws_instance.main.id
  }
}

# EC2 CPU Credits Alarm (critical for t3 burstable)
resource "aws_cloudwatch_metric_alarm" "ec2_cpu_credits" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${var.project_name}-ec2-cpu-credits-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUCreditBalance"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 20
  alarm_description   = "EC2 CPU credit balance < 20 (burstable performance at risk)"
  alarm_actions       = [aws_sns_topic.alarms[0].arn]

  dimensions = {
    InstanceId = aws_instance.main.id
  }
}

# EC2 Status Check Alarm
resource "aws_cloudwatch_metric_alarm" "ec2_status" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${var.project_name}-ec2-status-check"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "EC2 status check failed"
  alarm_actions       = [aws_sns_topic.alarms[0].arn]

  dimensions = {
    InstanceId = aws_instance.main.id
  }
}

# RDS CPU Alarm
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${var.project_name}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU utilization > 80%"
  alarm_actions       = [aws_sns_topic.alarms[0].arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }
}

# RDS Free Storage Alarm
resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${var.project_name}-rds-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 2147483648 # 2 GB in bytes
  alarm_description   = "RDS free storage < 2 GB"
  alarm_actions       = [aws_sns_topic.alarms[0].arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }
}

# RDS Connections Alarm
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  count               = var.alarm_email != "" ? 1 : 0
  alarm_name          = "${var.project_name}-rds-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80 # db.t4g.small has ~85 max connections
  alarm_description   = "RDS connections > 80 (approaching limit)"
  alarm_actions       = [aws_sns_topic.alarms[0].arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }
}
