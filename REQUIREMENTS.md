Create a frontend/backend tool that can show a complete tree view of my OCI cloud. I currently have 2 regions: Frankfurt and Stockholm.

I imagine a tree view like this:

- Region
  - Compartment
    - Networks (VCN/VPN/NSG...)
    - Instances
      - Backup
      - Disks
    - DB instances
      - Backup
      - Disks
    .
    .

Please elaborate on the tree structure your self.

The backend should be written in python3 and backend in react.

Each component in the treeview should have a direct link into the OCI web interface.

Any questions?

Rev. 1.1
On each object in the tree structure, please create an icon that upon click will open a detail box about the object. Also on each object please list the creation date.
As for backup information, please also include volume group information.

Rev. 1.2
Please include the OCID on each object. Upon click on the OCID please copy it to the paste buffer. Also include information about Network Security Lists and Groups.
Also - could you please cache the complete tree view for faster loads (you can the press "reload" manully). Please inform the the users of the age of the cached information.

Rev. 1.3
Please remove all compartment structures with no onjects in. This way only relevant compartments will be shown for each region.
Also - include information about Network Security Groups.

Rev. 1.4
Still cannot see NSGs anywhere. Please investigate/fix. Introduce a "reload" progress bar 

Rev. 1.5
The progress bar should not just be a spinning wheel, since this gives no indications as to how long it will take.

Rev. 1.6 
Please make the NSG/NSL list as a regular table instead of the more reader friendly text

Rev. 1.7
The NSG/NSL list should be sorted by "Source" as default. Clicking on the column header should change the sort to that column. Multiple clicks on the same column should toggle asc/desc. The column should also have a sorting indicator.

Rev. 1.8
Make sorting even better: When clicking on a second column while pressing ctrl, thiw should then extend this to include that column in the sort (like a primary and secondary sort order ... (and even more))

Rev. 1.9
Create a docker file.

Rev. 1.10
On each backup entry, it should be possible to see if a backup has failed. On the top compartment the failed backups should also be visible.
When clicking on the "information" button, an overview over the backups should be summarized. How many has failed, when was the last correct backup.

Rev. 1.11
Add an indicator for "missing backup" setups.