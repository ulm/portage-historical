import portage_const

def parseSyncUri(uri):
	u=uri.lower()
	if u.startswith("rsync") or len(u) == 0:
		if len(u) <= 5:
			return ('rsync',portage_const.RSYNC_HOST)
		return ('rsync',u[8:])
	elif u.startswith("cvs://"):
		u=u[6:]
		return ('cvs',u)
	elif u.startswith("snapshot"):
		if len(u)==8:
			# the caller gets to randomly crapshoot a mirror for it.
			return ('snapshot',None)
		return ('snapshot',u[9:])
	else:
		return (None,None)