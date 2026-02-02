
terraform apply \
  -var 'vpc_id=vpc-xxxx' \
  -var 'subnet_ids=["subnet-private-a","subnet-private-b"]' \
  -var 'alb_subnet_ids=["subnet-public-a","subnet-public-b"]' \
  -var 'permission_boundary_arn=arn:aws:iam::123456789012:policy/PermissionBoundary'

