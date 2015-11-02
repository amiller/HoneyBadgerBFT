def getAddrFromEC2Summary(s):
    return [
            x.split('ec2.')[-1] for x in s.replace(
                '.compute.amazonaws.com', ''
                ).replace(
                    '.us-west-1', ''    # Later we need to add more such lines
                    ).replace(
                        '-', '.'
                        ).strip().split('\n')]

from subprocess import check_output, Popen

def callFab(s, work):
    open('hosts','w').write('\n'.join(getAddrFromEC2Summary(s)))
    print Popen(['fab', '-i', '~/.ssh/amiller-mc2ec2.pem', 
        '-u', 'ubuntu', '-H', ','.join(getAddrFromEC2Summary(s)),
        work])

import IPython
IPython.embed()

